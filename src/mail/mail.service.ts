import { Injectable, Logger } from '@nestjs/common';
import {
  SESClient,
  SendEmailCommand,
  SendEmailCommandInput,
} from '@aws-sdk/client-ses';

@Injectable()
export class MailService {
  private readonly logger = new Logger(MailService.name);
  private readonly sesClient: SESClient;
  private readonly fromEmail: string;
  private readonly frontendUrl: string;

  constructor() {
    this.sesClient = new SESClient({ region: process.env.AWS_REGION ?? 'us-east-1' });
    this.fromEmail = process.env.SES_FROM_EMAIL ?? 'maxi.rodriguez.3105@gmail.com';
    this.frontendUrl = process.env.FRONTEND_URL ?? 'https://scrappy.io';
  }

  async sendPasswordResetEmail(email: string, token: string): Promise<void> {
    const resetLink = `${this.frontendUrl}/auth/reset-password?token=${token}`;

    const params: SendEmailCommandInput = {
      Source: this.fromEmail,
      Destination: { ToAddresses: [email] },
      Message: {
        Subject: { Data: 'Reset your Scrappy password', Charset: 'UTF-8' },
        Body: {
          Text: {
            Data: `You requested a password reset.\n\nClick the link below to reset your password (valid for 1 hour):\n\n${resetLink}\n\nIf you did not request this, ignore this email.`,
            Charset: 'UTF-8',
          },
          Html: {
            Data: `
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family: sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
  <h2>Reset your Scrappy password</h2>
  <p>You requested a password reset. Click the button below to reset your password (valid for 1 hour):</p>
  <a href="${resetLink}" style="display:inline-block;padding:12px 24px;background:#2563eb;color:#fff;text-decoration:none;border-radius:6px;font-weight:bold;">
    Reset Password
  </a>
  <p style="margin-top:24px;color:#6b7280;font-size:14px;">If you did not request this, you can safely ignore this email.</p>
</body>
</html>`,
            Charset: 'UTF-8',
          },
        },
      },
    };

    try {
      await this.sesClient.send(new SendEmailCommand(params));
      this.logger.log(`Password reset email sent to ${email}`);
    } catch (error) {
      this.logger.error(`Failed to send password reset email to ${email}`, error);
      throw error;
    }
  }
}
