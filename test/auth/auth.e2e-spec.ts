import { Test, TestingModule } from '@nestjs/testing';
import { INestApplication, ValidationPipe } from '@nestjs/common';
import * as request from 'supertest';
import { AppModule } from '../../src/app.module';
import { PrismaService } from '../../src/prisma/prisma.service';
import { HttpExceptionFilter } from '../../src/common/filters/http-exception.filter';

describe('Auth (e2e)', () => {
  let app: INestApplication;
  let prisma: PrismaService;

  const testEmail = `test-${Date.now()}@example.com`;
  const testPassword = 'Password123!';

  beforeAll(async () => {
    const moduleFixture: TestingModule = await Test.createTestingModule({
      imports: [AppModule],
    }).compile();

    app = moduleFixture.createNestApplication();
    app.useGlobalPipes(
      new ValidationPipe({ whitelist: true, forbidNonWhitelisted: true, transform: true }),
    );
    app.useGlobalFilters(new HttpExceptionFilter());
    await app.init();

    prisma = moduleFixture.get<PrismaService>(PrismaService);
  });

  afterAll(async () => {
    // Clean up test user
    await prisma.user.deleteMany({ where: { email: testEmail } });
    await app.close();
  });

  describe('POST /auth/signup', () => {
    it('creates a user and returns token pair', async () => {
      const res = await request(app.getHttpServer())
        .post('/auth/signup')
        .send({ email: testEmail, password: testPassword, fullName: 'Test User' })
        .expect(201);

      expect(res.body).toHaveProperty('access_token');
      expect(res.body).toHaveProperty('refresh_token');
      expect(typeof res.body.access_token).toBe('string');
      expect(typeof res.body.refresh_token).toBe('string');
    });

    it('returns 409 if email already registered', async () => {
      await request(app.getHttpServer())
        .post('/auth/signup')
        .send({ email: testEmail, password: testPassword })
        .expect(409);
    });

    it('returns 400 for invalid email', async () => {
      await request(app.getHttpServer())
        .post('/auth/signup')
        .send({ email: 'not-an-email', password: testPassword })
        .expect(400);
    });

    it('returns 400 for short password', async () => {
      await request(app.getHttpServer())
        .post('/auth/signup')
        .send({ email: 'new@example.com', password: 'short' })
        .expect(400);
    });
  });

  describe('POST /auth/login', () => {
    let accessToken: string;
    let refreshToken: string;

    it('returns token pair for valid credentials', async () => {
      const res = await request(app.getHttpServer())
        .post('/auth/login')
        .send({ email: testEmail, password: testPassword })
        .expect(200);

      expect(res.body).toHaveProperty('access_token');
      expect(res.body).toHaveProperty('refresh_token');
      accessToken = res.body.access_token as string;
      refreshToken = res.body.refresh_token as string;
    });

    it('returns 401 for wrong password', async () => {
      await request(app.getHttpServer())
        .post('/auth/login')
        .send({ email: testEmail, password: 'WrongPass1!' })
        .expect(401);
    });

    it('returns 401 for unknown email', async () => {
      await request(app.getHttpServer())
        .post('/auth/login')
        .send({ email: 'nobody@example.com', password: testPassword })
        .expect(401);
    });

    describe('POST /auth/logout', () => {
      it('logs out successfully with valid access token and refresh token', async () => {
        await request(app.getHttpServer())
          .post('/auth/logout')
          .set('Authorization', `Bearer ${accessToken}`)
          .send({ refresh_token: refreshToken })
          .expect(204);
      });
    });
  });

  describe('POST /auth/refresh', () => {
    it('issues new token pair from valid refresh token', async () => {
      // First login to get a fresh refresh token
      const loginRes = await request(app.getHttpServer())
        .post('/auth/login')
        .send({ email: testEmail, password: testPassword })
        .expect(200);

      const refreshToken = loginRes.body.refresh_token as string;

      const res = await request(app.getHttpServer())
        .post('/auth/refresh')
        .send({ refresh_token: refreshToken })
        .expect(200);

      expect(res.body).toHaveProperty('access_token');
      expect(res.body).toHaveProperty('refresh_token');
      // Refresh token should be rotated
      expect(res.body.refresh_token).not.toBe(refreshToken);
    });

    it('returns 401 for invalid refresh token', async () => {
      await request(app.getHttpServer())
        .post('/auth/refresh')
        .send({ refresh_token: 'invalid-token' })
        .expect(401);
    });
  });

  describe('POST /auth/forgot-password', () => {
    it('returns 204 for existing email (no email actually sent in test)', async () => {
      await request(app.getHttpServer())
        .post('/auth/forgot-password')
        .send({ email: testEmail })
        .expect(204);
    });

    it('returns 204 for non-existent email (security: no leak)', async () => {
      await request(app.getHttpServer())
        .post('/auth/forgot-password')
        .send({ email: 'nonexistent@example.com' })
        .expect(204);
    });
  });
});
