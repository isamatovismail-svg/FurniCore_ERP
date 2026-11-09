import { Injectable, UnauthorizedException } from '@nestjs/common';
import { JwtService } from '@nestjs/jwt';
import { PrismaService } from '../prisma/prisma.service';
import bcrypt from 'bcryptjs';

@Injectable()
export class AuthService {
  constructor(
    private prisma: PrismaService,
    private jwtService: JwtService,
  ) {}

  async validateUser(email: string, pass: string) {
    const user = await this.prisma.user.findUnique({
      where: { email },
    });
    if (user && user.isActive) {
      const match = await bcrypt.compare(pass, user.passwordHash);
      if (match) {
        // eslint-disable-next-line @typescript-eslint/no-unused-vars
        const { passwordHash, ...result } = user;
        return result;
      }
    }
    return null;
  }

  async login(loginDto: { email: string; pass: string }) {
    const user = await this.validateUser(loginDto.email, loginDto.pass);
    if (!user) {
      throw new UnauthorizedException('Неверный логин или пароль');
    }
    const payload = { email: user.email, sub: user.id, role: user.role };
    return {
      accessToken: this.jwtService.sign(payload),
      user,
    };
  }
}
