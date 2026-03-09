# Scrappy — Guía de Despliegue en Producción

Instrucciones paso a paso para desplegar Scrappy desde cero.
Seguir las fases **en orden** — cada una depende de la anterior.

**Stack**: NestJS 10 · TypeScript · Prisma · PostgreSQL (AWS RDS) · JWT · AWS SES · AWS Lambda (nodejs22.x) · API Gateway HTTP · SAM

---

## Prerrequisitos

Instalar y configurar las siguientes herramientas:

```bash
# AWS CLI
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip && sudo ./aws/install

# Configurar con credenciales de usuario admin
aws configure
# AWS Access Key ID: [tu clave]
# AWS Secret Access Key: [tu secreto]
# Default region: us-east-1
# Default output format: json

# AWS SAM CLI
pip install aws-sam-cli

# Node.js 22 (LTS)
# Recomendado: usar nvm
nvm install 22 && nvm use 22
```

Verificar:
```bash
aws --version    # aws-cli/2.x.x
sam --version    # SAM CLI, version 1.x.x
node --version   # v22.x.x
```

---

## Fase 1 — Base de datos (AWS RDS PostgreSQL)

### 1.1 Crear la instancia RDS

1. Ir a **AWS Console → RDS → Create database**.
2. Configurar:
   - **Engine**: PostgreSQL (última versión estable)
   - **Template**: Free tier (para desarrollo) o Production
   - **DB instance identifier**: `scrappy-db`
   - **Username**: `scrappy`
   - **Password**: generar una contraseña fuerte y guardarla
   - **Region**: `us-east-1`
3. En **Connectivity**:
   - Habilitar acceso público solo si necesitás correr migraciones desde local (se puede deshabilitar después)
   - Anotar el **Endpoint** al finalizar, por ejemplo: `scrappy-db.xxxx.us-east-1.rds.amazonaws.com`

### 1.2 Construir la connection string

```
postgresql://scrappy:[PASSWORD]@scrappy-db.xxxx.us-east-1.rds.amazonaws.com:5432/scrappy
```

Guardar este valor — se va a almacenar en SSM como `/scrappy/database-url`.

### 1.3 Correr las migraciones

Con acceso a la base de datos desde local:

```bash
# Desde la raíz del proyecto
DATABASE_URL="postgresql://scrappy:[PASSWORD]@scrappy-db.xxxx.us-east-1.rds.amazonaws.com:5432/scrappy" \
  npx prisma migrate deploy
```

Salida esperada:
```
Applying migration `20240101000000_init`
All migrations have been applied.
```

> Repetir este paso cada vez que se agregue una nueva migración al proyecto.

---

## Fase 2 — AWS SES (emails)

El backend usa SES para enviar emails de recuperación de contraseña.

### 2.1 Verificar el email remitente

```bash
aws ses verify-email-identity \
  --email-address noreply@tudominio.com \
  --region us-east-1
```

AWS envía un email de confirmación a esa dirección. Hacer clic en el enlace de verificación.

### 2.2 Salir del modo sandbox (producción)

Por defecto, SES solo puede enviar a emails verificados (sandbox). Para enviar a cualquier destinatario:

1. Ir a **AWS Console → SES → Account dashboard**.
2. Hacer clic en **Request production access**.
3. Completar el formulario indicando el caso de uso. AWS aprueba en 24-48hs.

> Para desarrollo/testing el sandbox es suficiente, siempre que verifiques también los emails destinatarios.

---

## Fase 3 — Secrets en SSM Parameter Store

Todos los secretos se guardan en SSM para que nunca estén hardcodeados en el código ni en el template de SAM.

```bash
# Connection string de la base de datos
aws ssm put-parameter \
  --name /scrappy/database-url \
  --value "postgresql://scrappy:[PASSWORD]@scrappy-db.xxxx.us-east-1.rds.amazonaws.com:5432/scrappy" \
  --type SecureString \
  --region us-east-1

# Secret para firmar los access tokens JWT
aws ssm put-parameter \
  --name /scrappy/jwt-secret \
  --value "$(openssl rand -base64 48)" \
  --type SecureString \
  --region us-east-1

# Secret para firmar los refresh tokens JWT
aws ssm put-parameter \
  --name /scrappy/jwt-refresh-secret \
  --value "$(openssl rand -base64 48)" \
  --type SecureString \
  --region us-east-1

# Email remitente verificado en SES
aws ssm put-parameter \
  --name /scrappy/ses-from-email \
  --value "noreply@tudominio.com" \
  --type SecureString \
  --region us-east-1

# URL del frontend (usada para CORS y links en emails)
aws ssm put-parameter \
  --name /scrappy/frontend-url \
  --value "https://tuapp.vercel.app" \
  --type SecureString \
  --region us-east-1
```

Verificar que se crearon todos:
```bash
aws ssm describe-parameters \
  --parameter-filters "Key=Path,Values=/scrappy" \
  --query "Parameters[*].Name" \
  --region us-east-1
```

Salida esperada:
```json
[
  "/scrappy/database-url",
  "/scrappy/frontend-url",
  "/scrappy/jwt-refresh-secret",
  "/scrappy/jwt-secret",
  "/scrappy/ses-from-email"
]
```

---

## Fase 4 — Primer deploy con SAM

SAM provisiona toda la infraestructura AWS: Lambda, API Gateway HTTP, y los permisos IAM necesarios.

### 4.1 Build

```bash
# Compilar TypeScript
npm run build

# Empaquetar con esbuild (sin Docker)
sam build
```

### 4.2 Deploy guiado (primera vez)

```bash
sam deploy --guided
```

Responder los prompts:
```
Stack Name [sam-app]: scrappy-backend
AWS Region [us-east-1]: us-east-1
Confirm changes before deploy [y/N]: y
Allow SAM CLI IAM role creation [Y/n]: Y
Disable rollback [y/N]: N
Save arguments to configuration file [Y/n]: Y
SAM configuration file [samconfig.toml]: samconfig.toml
SAM configuration environment [default]: default
```

SAM muestra un changeset. Revisar y confirmar con `y`.

El deploy tarda ~2-3 minutos. Al finalizar, anotar los **Outputs**:

```
Key         ApiUrl
Value       https://[ID].execute-api.us-east-1.amazonaws.com

Key         FunctionArn
Value       arn:aws:lambda:us-east-1:[ACCOUNT]:function:scrappy-api
```

### 4.3 Verificar que la API responde

```bash
curl https://[ID].execute-api.us-east-1.amazonaws.com/auth/health
# o cualquier endpoint público
```

---

## Fase 5 — Rol IAM para GitHub Actions (OIDC)

GitHub Actions se autentica con AWS usando tokens de corta duración (OIDC), sin necesidad de guardar credenciales en GitHub.

### 5.1 Registrar el OIDC provider de GitHub en AWS

Esto se hace una sola vez por cuenta AWS:

```bash
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1 \
  --region us-east-1
```

Verificar:
```bash
aws iam list-open-id-connect-providers
```

### 5.2 Crear el trust policy

Crear el archivo `trust-policy.json` (reemplazar `[ACCOUNT-ID]`):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::[ACCOUNT-ID]:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:maxi-89/scrappy-backend:*"
        }
      }
    }
  ]
}
```

### 5.3 Crear el rol

```bash
aws iam create-role \
  --role-name scrappy-github-deploy \
  --assume-role-policy-document file://trust-policy.json
```

Anotar el `Arn` del output:
```
arn:aws:iam::[ACCOUNT-ID]:role/scrappy-github-deploy
```

### 5.4 Crear y adjuntar la policy de permisos

Crear el archivo `deploy-policy.json` (reemplazar `[ACCOUNT-ID]`):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "LambdaDeploy",
      "Effect": "Allow",
      "Action": [
        "lambda:UpdateFunctionCode",
        "lambda:GetFunction",
        "lambda:GetFunctionConfiguration"
      ],
      "Resource": "arn:aws:lambda:us-east-1:[ACCOUNT-ID]:function:scrappy-api"
    },
    {
      "Sid": "SAMBucket",
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject"
      ],
      "Resource": "arn:aws:s3:::aws-sam-cli-managed-default-samclisourcebucket-*/*"
    }
  ]
}
```

```bash
aws iam put-role-policy \
  --role-name scrappy-github-deploy \
  --policy-name scrappy-deploy-policy \
  --policy-document file://deploy-policy.json
```

---

## Fase 6 — Secret en GitHub

1. Ir al repositorio en GitHub: `github.com/maxi-89/scrappy-backend`
2. Ir a **Settings → Secrets and variables → Actions**.
3. Hacer clic en **New repository secret**.
4. Completar:
   - **Name**: `AWS_DEPLOY_ROLE_ARN`
   - **Value**: `arn:aws:iam::[ACCOUNT-ID]:role/scrappy-github-deploy`
5. Hacer clic en **Add secret**.

---

## Fase 7 — Primer release

Disparar el pipeline de CI/CD pusheando un tag a `master`:

```bash
git tag v1.0.0
git push origin v1.0.0
```

Seguir el pipeline en:
```
https://github.com/maxi-89/scrappy-backend/actions
```

El pipeline corre dos jobs en secuencia:
1. **Tests** — unit tests con Jest (debe pasar antes del deploy)
2. **Deploy** — `npm run build` + `sam build` + `sam deploy`

---

## Fase 8 — Dominio personalizado (opcional)

Esta fase configura `api.scrappy.io` en lugar de la URL autogenerada de API Gateway.

### 8.1 Registrar o transferir el dominio a Route 53

**Opción A — Registrar un dominio nuevo en Route 53:**
1. Ir a **AWS Console → Route 53 → Domains → Register domain**.
2. Buscar `scrappy.io`, seleccionarlo y completar la compra.
3. Route 53 crea automáticamente una **Hosted Zone**.

**Opción B — Dominio registrado en otro proveedor (GoDaddy, Namecheap, etc.):**
1. Ir a **Route 53 → Hosted zones → Create hosted zone**.
2. Completar:
   - **Domain name**: `scrappy.io`
   - **Type**: Public hosted zone
3. Route 53 muestra 4 registros **NS**, por ejemplo:
   ```
   ns-123.awsdns-12.com
   ns-456.awsdns-34.net
   ns-789.awsdns-56.org
   ns-012.awsdns-78.co.uk
   ```
4. En el registrador del dominio, reemplazar los nameservers con estos 4 valores.
5. La propagación DNS tarda entre 10 minutos y 48 horas.

### 8.2 Solicitar certificado SSL en ACM

API Gateway requiere un certificado ACM **en `us-east-1`**:

```bash
aws acm request-certificate \
  --domain-name "scrappy.io" \
  --subject-alternative-names "*.scrappy.io" \
  --validation-method DNS \
  --region us-east-1
```

Anotar el `CertificateArn` del output.

**Validar el certificado por DNS:**

```bash
aws acm describe-certificate \
  --certificate-arn arn:aws:acm:us-east-1:[ACCOUNT]:certificate/[ID] \
  --region us-east-1 \
  --query "Certificate.DomainValidationOptions[0].ResourceRecord"
```

Output:
```json
{
  "Name": "_abc123.scrappy.io.",
  "Type": "CNAME",
  "Value": "_def456.acm-validations.aws."
}
```

Agregar el registro CNAME en Route 53:
```bash
# Obtener el Hosted Zone ID
aws route53 list-hosted-zones \
  --query "HostedZones[?Name=='scrappy.io.'].Id" \
  --output text
# Retorna: /hostedzone/[ZONE-ID]

aws route53 change-resource-record-sets \
  --hosted-zone-id [ZONE-ID] \
  --change-batch '{
    "Changes": [{
      "Action": "CREATE",
      "ResourceRecordSet": {
        "Name": "_abc123.scrappy.io.",
        "Type": "CNAME",
        "TTL": 300,
        "ResourceRecords": [{"Value": "_def456.acm-validations.aws."}]
      }
    }]
  }'
```

Esperar la validación (~2-5 minutos):
```bash
aws acm wait certificate-validated \
  --certificate-arn arn:aws:acm:us-east-1:[ACCOUNT]:certificate/[ID] \
  --region us-east-1
```

### 8.3 Crear dominio personalizado en API Gateway

1. Ir a **AWS Console → API Gateway → Custom domain names → Create**.
2. Completar:
   - **Domain name**: `api.scrappy.io`
   - **ACM certificate**: seleccionar el certificado creado en 8.2
3. Hacer clic en **Create domain name**.
4. Anotar el **API Gateway domain name** generado, por ejemplo:
   ```
   d-abc123xyz.execute-api.us-east-1.amazonaws.com
   ```

**Mapear el dominio al API stage:**
1. En el detalle del dominio, hacer clic en **API mappings → Add new mapping**.
2. Seleccionar el API y el stage (`$default`).
3. Dejar **Path** vacío (mapea la raíz).
4. Hacer clic en **Save**.

### 8.4 Apuntar api.scrappy.io a API Gateway (Route 53)

```bash
aws route53 change-resource-record-sets \
  --hosted-zone-id [ZONE-ID] \
  --change-batch '{
    "Changes": [{
      "Action": "CREATE",
      "ResourceRecordSet": {
        "Name": "api.scrappy.io.",
        "Type": "A",
        "AliasTarget": {
          "HostedZoneId": "Z2FDTNDATAQYW2",
          "DNSName": "d-abc123xyz.execute-api.us-east-1.amazonaws.com.",
          "EvaluateTargetHealth": false
        }
      }
    }]
  }'
```

> `Z2FDTNDATAQYW2` es el Hosted Zone ID fijo de API Gateway para Route 53, siempre es este valor independientemente de la región.

Verificar (esperar 1-2 minutos para DNS):
```bash
curl https://api.scrappy.io/auth/health
```

### 8.5 Actualizar el parámetro frontend-url en SSM

Si el frontend ya tiene dominio final:
```bash
aws ssm put-parameter \
  --name /scrappy/frontend-url \
  --value "https://scrappy.io" \
  --type SecureString \
  --overwrite \
  --region us-east-1
```

Luego volver a hacer deploy para que Lambda tome el nuevo valor:
```bash
sam build && sam deploy
```

---

## Checklist de verificación final

```bash
# 1. La API responde
curl https://[ID].execute-api.us-east-1.amazonaws.com/auth/health
# o con dominio personalizado:
curl https://api.scrappy.io/auth/health

# 2. Registro de usuario funciona
curl -X POST https://api.scrappy.io/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@test.com","password":"Test1234!","fullName":"Test User"}'

# 3. Ver logs en tiempo real (CloudWatch)
aws logs tail /aws/lambda/scrappy-api --follow --region us-east-1
```

---

## Releases posteriores

Para todos los deploys futuros de código:

```bash
git tag v1.0.1
git push origin v1.0.1
```

El pipeline de GitHub Actions se encarga del resto.

**Cambios de infraestructura** (modificar `template.yaml`) requieren correr SAM manualmente:
```bash
npm run build && sam build && sam deploy
```

**Nuevas migraciones de base de datos** requieren correr Prisma manualmente:
```bash
DATABASE_URL="..." npx prisma migrate deploy
```

---

## Referencia: qué herramienta despliega qué

| Herramienta | Provisiona | Cuándo correr |
|---|---|---|
| `npx prisma migrate deploy` | Tablas en RDS | Primer deploy + cada nueva migración |
| `sam build && sam deploy` | Lambda, API Gateway, IAM roles | Primer deploy + cambios en `template.yaml` |
| `git tag + push` (CI/CD) | Código de la Lambda | Cada release de código |

## Referencia: variables de entorno

| Variable | Parámetro SSM | Descripción |
|---|---|---|
| `DATABASE_URL` | `/scrappy/database-url` | Connection string de PostgreSQL (RDS) |
| `JWT_SECRET` | `/scrappy/jwt-secret` | Secret para firmar access tokens |
| `JWT_REFRESH_SECRET` | `/scrappy/jwt-refresh-secret` | Secret para firmar refresh tokens |
| `SES_FROM_EMAIL` | `/scrappy/ses-from-email` | Email remitente verificado en SES |
| `FRONTEND_URL` | `/scrappy/frontend-url` | URL del frontend (CORS + links en emails) |
