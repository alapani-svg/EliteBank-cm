import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink, RouterLinkActive, Router } from '@angular/router';
import {
  ReactiveFormsModule, FormBuilder, FormGroup, Validators
} from '@angular/forms';
import { HttpErrorResponse } from '@angular/common/http';
import { TransactionService } from '../../../services/transaction.service';
import { UserService } from '../../../services/user.service';
import { AuthService } from '../../../services/auth.service';
import { BeneficiaryService } from '../../../services/beneficiary.service';
import { NotificationService } from '../../../services/notification.service';
import { NotifBell } from '../../../components/notif-bell/notif-bell';
import { UserAvatar } from '../../../components/user-avatar/user-avatar';
import { TPipe } from '../../../pipes/t.pipe';
import { User } from '../../../models/user.model';
import { Beneficiary } from '../../../models/transaction.model';

@Component({
  selector: 'app-transfer',
  standalone: true,
  imports: [CommonModule, RouterLink, RouterLinkActive, ReactiveFormsModule, NotifBell, UserAvatar, TPipe],
  templateUrl: './transfer.html',
  styleUrl: './transfer.scss',
})
export class Transfer implements OnInit {

  form!: FormGroup;
  loading = false;
  success = '';
  error   = '';
  fieldErrors: Record<string, string> = {};
  user: User | null = null;
  sidebarOpen = false;

  beneficiaries: Beneficiary[] = [];
  saveLoading = false;
  saveSuccess = '';
  showSavePrompt = false;
  lastTransferIdentifier = '';

  constructor(
    private fb: FormBuilder,
    private txService: TransactionService,
    private userService: UserService,
    private bService: BeneficiaryService,
    private notifications: NotificationService,
    private auth: AuthService,
    private router: Router,
  ) {}

  ngOnInit(): void {
    this.form = this.fb.group({
      recipient_identifier: ['', [Validators.required]],
      amount: ['', [Validators.required, Validators.min(100)]],
      description: [''],
    });

    this.userService.getProfile().subscribe({ next: (u) => this.user = u });
    this.loadBeneficiaries();
  }

  loadBeneficiaries(): void {
    this.bService.list('TRANSFER').subscribe({
      next: (list) => this.beneficiaries = list,
      error: () => { /* non-critical */ },
    });
  }

  pickBeneficiary(b: Beneficiary): void {
    this.form.patchValue({ recipient_identifier: b.identifier });
  }

  get f() { return this.form.controls; }

  submit(): void {
    if (this.form.invalid || this.loading) return;

    this.loading     = true;
    this.success     = '';
    this.error       = '';
    this.fieldErrors = {};
    this.showSavePrompt = false;

    const identifier = this.form.value.recipient_identifier;

    this.txService.transfer(this.form.value).subscribe({
      next: () => {
        this.loading = false;
        this.success = 'Transfer successful!';
        this.lastTransferIdentifier = identifier;
        // Show "save beneficiary" prompt only if it's not already saved
        this.showSavePrompt = !this.beneficiaries.some(b => b.identifier === identifier);
        this.form.reset();
        this.userService.getProfile().subscribe({ next: (u) => this.user = u });
        this.notifications.refresh();
        if (!this.showSavePrompt) {
          setTimeout(() => this.router.navigate(['/transactions']), 2000);
        }
      },
      error: (err: HttpErrorResponse) => {
        this.loading = false;
        this.parseErrors(err);
      },
    });
  }

  saveBeneficiary(name: string): void {
    if (!name.trim() || !this.lastTransferIdentifier) return;
    this.saveLoading = true;
    this.bService.create({
      name: name.trim(),
      identifier: this.lastTransferIdentifier,
      category: 'TRANSFER',
    }).subscribe({
      next: (b) => {
        this.saveLoading = false;
        this.saveSuccess = `${b.name} saved to your beneficiaries.`;
        this.beneficiaries = [b, ...this.beneficiaries];
        this.showSavePrompt = false;
        setTimeout(() => this.router.navigate(['/transactions']), 1500);
      },
      error: () => {
        this.saveLoading = false;
        this.saveSuccess = '';
      },
    });
  }

  dismissSavePrompt(): void {
    this.showSavePrompt = false;
    setTimeout(() => this.router.navigate(['/transactions']), 500);
  }

  toggleSidebar(): void { this.sidebarOpen = !this.sidebarOpen; }
  closeSidebar():  void { this.sidebarOpen = false; }
  logout():        void { this.auth.logout(); }

  private parseErrors(err: HttpErrorResponse): void {
    if (!err.error) { this.error = 'An unexpected error occurred.'; return; }
    if (err.error.detail) { this.error = err.error.detail; return; }
    if (typeof err.error === 'string') { this.error = err.error; return; }

    const knownFields = ['recipient_identifier', 'amount', 'description'];
    const general: string[] = [];

    for (const key of Object.keys(err.error)) {
      const msg = Array.isArray(err.error[key]) ? err.error[key].join(' ') : String(err.error[key]);
      if (knownFields.includes(key)) {
        this.fieldErrors[key] = msg;
      } else {
        general.push(msg);
      }
    }

    if (general.length) this.error = general.join(' | ');
  }
}
