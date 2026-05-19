import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink, RouterLinkActive, Router } from '@angular/router';
import { ReactiveFormsModule, FormBuilder, FormGroup, Validators } from '@angular/forms';
import { HttpErrorResponse } from '@angular/common/http';
import { TransactionService } from '../../../services/transaction.service';
import { UserService } from '../../../services/user.service';
import { AuthService } from '../../../services/auth.service';
import { NotificationService } from '../../../services/notification.service';
import { NotifBell } from '../../../components/notif-bell/notif-bell';
import { TPipe } from '../../../pipes/t.pipe';
import { UserAvatar } from '../../../components/user-avatar/user-avatar';
import { User } from '../../../models/user.model';
import { PaymentMethod } from '../../../models/transaction.model';

type WithdrawStep = 'form' | 'processing' | 'success' | 'error';

@Component({
  selector: 'app-withdrawal',
  standalone: true,
  imports: [CommonModule, RouterLink, RouterLinkActive, ReactiveFormsModule, NotifBell, UserAvatar, TPipe],
  templateUrl: './withdrawal.html',
  styleUrl:    './withdrawal.scss',
})
export class Withdrawal implements OnInit {

  step: WithdrawStep = 'form';
  form!: FormGroup;
  user: User | null = null;
  sidebarOpen = false;

  selectedProvider: PaymentMethod = 'orange';
  quickAmounts = [1000, 5000, 10000, 25000, 50000, 100000];

  successMessage = '';
  errorMessage   = '';
  completedRef   = '';

  constructor(
    private fb:            FormBuilder,
    private txService:     TransactionService,
    private userService:   UserService,
    private notifications: NotificationService,
    private auth:          AuthService,
    private router:        Router,
  ) {}

  ngOnInit(): void {
    this.form = this.fb.group({
      amount: ['', [Validators.required, Validators.min(500)]],
      phone:  ['', [Validators.required, Validators.pattern(/^\+?237[0-9]{8,9}$/)]],
    });

    this.userService.getProfile().subscribe({
      next: (u) => {
        this.user = u;
        if (u.phone_number) this.form.patchValue({ phone: u.phone_number });
      },
    });
  }

  get f() { return this.form.controls; }

  selectProvider(p: PaymentMethod): void { this.selectedProvider = p; }

  setAmount(v: number): void {
    this.form.patchValue({ amount: v });
    this.form.controls['amount'].markAsTouched();
  }

  get providerLabel(): string {
    return this.selectedProvider === 'orange' ? 'Orange Money' : 'MTN Mobile Money';
  }

  get insufficientFunds(): boolean {
    const amount = Number(this.form?.value?.amount || 0);
    return !!(this.user && amount > Number(this.user.balance_xaf));
  }

  submit(): void {
    if (this.form.invalid || this.insufficientFunds) {
      this.form.markAllAsTouched();
      return;
    }

    this.step         = 'processing';
    this.errorMessage = '';

    this.txService.withdraw({
      amount:         this.form.value.amount,
      phone:          this.form.value.phone,
      payment_method: this.selectedProvider,
    }).subscribe({
      next: (res) => {
        this.successMessage = res.message;
        this.completedRef   = res.reference;
        this.step           = 'success';
        this.userService.getProfile().subscribe({ next: (u) => this.user = u });
        this.notifications.refresh();
      },
      error: (err: HttpErrorResponse) => {
        this.errorMessage = this.parseError(err);
        this.step         = 'error';
      },
    });
  }

  retry(): void {
    this.step         = 'form';
    this.errorMessage = '';
    this.completedRef = '';
  }

  toggleSidebar(): void { this.sidebarOpen = !this.sidebarOpen; }
  closeSidebar():  void { this.sidebarOpen = false; }
  logout():        void { this.auth.logout(); }

  private parseError(err: HttpErrorResponse): string {
    if (!err.error) return 'An unexpected error occurred.';
    if (err.error.detail) return err.error.detail;
    if (typeof err.error === 'string') return err.error;
    const msgs: string[] = [];
    for (const k of Object.keys(err.error)) {
      const v = err.error[k];
      msgs.push(Array.isArray(v) ? v.join(' ') : String(v));
    }
    return msgs.join(' | ') || 'Withdrawal failed.';
  }
}
