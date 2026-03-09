import { Injectable } from '@nestjs/common';
import { User } from '@prisma/client';
import { UsersRepository } from './users.repository';

@Injectable()
export class UsersService {
  constructor(private readonly usersRepository: UsersRepository) {}

  async findByEmail(email: string): Promise<User | null> {
    return this.usersRepository.findByEmail(email);
  }

  async findById(id: string): Promise<User | null> {
    return this.usersRepository.findById(id);
  }

  async create(data: {
    email: string;
    passwordHash: string;
    fullName?: string;
  }): Promise<User> {
    return this.usersRepository.create(data);
  }

  async updatePassword(id: string, passwordHash: string): Promise<User> {
    return this.usersRepository.updatePassword(id, passwordHash);
  }
}
