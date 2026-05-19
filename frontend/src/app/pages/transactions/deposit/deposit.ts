import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink, RouterLinkActive } from '@angular/router';
import { ReactiveFormsModule, FormBuilder, FormGroup, Validators } from '@angular/forms';
import { HttpErrorResponse } from '@angular/common/http';
import { TransactionService } from '../../../services/transaction.service';
import { UserService } from '../../../services/user.service';
import { AuthService } from '../../../services/auth.service';
import { NotificationService } from '../../../services/notification.service';
import { NotifBell } from '../../../components/notif-bell/notif-bell';
import { UserAvatar } from '../../../components/user-avatar/user-avatar';
import { TPipe } from '../../../pipes/t.pipe';
import { User } from '../../../models/user.model';
import { PaymentMethod } from '../../../models/transaction.model';

type DepositStep = 'form' | 'processing' | 'success' | 'error';

@Component({
  selector: 'app-deposit',
  standalone: true,
  imports: [CommonModule, RouterLink, RouterLinkActive, ReactiveFormsModule, NotifBell, UserAvatar, TPipe],
  templateUrl: './deposit.html',
  styleUrl:    './deposit.scss',
})
export class Deposit implements OnInit, OnDestroy {

  step: DepositStep = 'form';
  form!: FormGroup;
  user: User | null = null;
  sidebarOpen = false;

  selectedProvider: PaymentMethod = 'orange';
  quickAmounts = [500, 1000, 5000, 10000, 25000, 50000];

  successMessage = '';
  errorMessage   = '';
  pendingRef     = '';

  private pollTimer: ReturnType<typeof setInterval> | null = null;
  private pollCount = 0;
  private readonly MAX_POLLS = 20;

  constructor(
    private fb: FormBuilder,
    private txService: TransactionService,
    private userService: UserService,
    private notifications: NotificationService,
    private auth: AuthService,
  ) {}

  ngOnInit(): void {
    this.form = this.fb.group({
      amount: ['', [Validators.required, Validators.min(100)]],
      phone:  ['', [Validators.required,
                    Validators.pattern(/^\+?237[0-9]{8,9}$/)]],
    });

    this.userService.getProfile().subscribe({
      next: (u) => {
        this.user = u;
        if (u.phone_number) {
          this.form.patchValue({ phone: u.phone_number });
        }
      },
    });
  }

  ngOnDestroy(): void {
    this.stopPolling();
  }

  get f() { return this.form.controls; }

  selectProvider(p: PaymentMethod): void {
    this.selectedProvider = p;
  }

  setAmount(v: number): void {
    this.form.patchValue({ amount: v });
    this.form.controls['amount'].markAsTouched();
  }

  submit(): void {
    if (this.form.invalid) { this.form.markAllAsTouched(); return; }

    this.step         = 'processing';
    this.errorMessage = '';

    this.txService.initiateDeposit({
      amount:         this.form.value.amount,
      phone:          this.form.value.phone,
      payment_method: this.selectedProvider,
    }).subscribe({
      next: (res) => {
        if (res.status === 'completed') {
          this.successMessage = res.message;
          this.step           = 'success';
          this.refreshBalance();
          this.notifications.refresh();
        } else if (res.status === 'pending') {
          this.pendingRef = res.reference;
          this.startPolling();
        } else {
          this.errorMessage = res.message || 'Deposit failed. Please try again.';
          this.step         = 'error';
        }
      },
      error: (err: HttpErrorResponse) => {
        this.errorMessage = err.error?.detail || 'Payment gateway error. Please try again.';
        this.step         = 'error';
      },
    });
  }

  retry(): void {
    this.stopPolling();
    this.step         = 'form';
    this.errorMessage = '';
    this.pendingRef   = '';
    this.pollCount    = 0;
  }

  toggleSidebar(): void { this.sidebarOpen = !this.sidebarOpen; }
  closeSidebar():  void { this.sidebarOpen = false; }
  logout():        void { this.auth.logout(); }

  private startPolling(): void {
    this.pollCount = 0;
    this.pollTimer = setInterval(() => {
      this.pollCount++;
      this.txService.checkDepositStatus(this.pendingRef).subscribe({
        next: (res) => {
          if (res.status === 'completed') {
            this.stopPolling();
            this.successMessage = `XAF ${Number(res.transaction.amount).toLocaleString('fr-CM')} added to your account!`;
            this.step           = 'success';
            this.notifications.refresh();
            this.refreshBalance();
          } else if (res.status === 'failed') {
            this.stopPolling();
            this.errorMessage = 'Payment was declined or timed out. Please try again.';
            this.step         = 'error';
          } else if (this.pollCount >= this.MAX_POLLS) {
            this.stopPolling();
            this.errorMessage = 'Payment is taking too long. Please check your phone and try again.';
            this.step         = 'error';
          }
        },
      });
    }, 3000);
  }

  private stopPolling(): void {
    if (this.pollTimer) {
      clearInterval(this.pollTimer);
      this.pollTimer = null;
    }
  }

  private refreshBalance(): void {
    this.userService.getProfile().subscribe({ next: (u) => this.user = u });
  }

  get providerLabel(): string {
    return this.selectedProvider === 'orange' ? 'Orange Money' : 'MTN Mobile Money';
  }

  get depositedAmount(): string {
    return Number(this.form.value.amount).toLocaleString('fr-CM');
  }
}
