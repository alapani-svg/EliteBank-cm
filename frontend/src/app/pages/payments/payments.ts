import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink, RouterLinkActive } from '@angular/router';
import { ReactiveFormsModule, FormsModule, FormBuilder, FormGroup, Validators } from '@angular/forms';
import { HttpErrorResponse } from '@angular/common/http';
import { TransactionService } from '../../services/transaction.service';
import { UserService } from '../../services/user.service';
import { AuthService } from '../../services/auth.service';
import { BeneficiaryService } from '../../services/beneficiary.service';
import { NotificationService } from '../../services/notification.service';
import { NotifBell } from '../../components/notif-bell/notif-bell';
import { UserAvatar } from '../../components/user-avatar/user-avatar';
import { TPipe } from '../../pipes/t.pipe';
import { Transaction, BillProvider, Beneficiary } from '../../models/transaction.model';
import { User } from '../../models/user.model';

interface BillProviderConfig {
  id:    BillProvider;
  label: string;
  icon:  string;
  color: string;
}

@Component({
  selector: 'app-payments',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink, RouterLinkActive, ReactiveFormsModule, NotifBell, UserAvatar, TPipe],
  templateUrl: './payments.html',
  styleUrl:    './payments.scss',
})
export class Payments implements OnInit {

  user:        User | null = null;
  sidebarOpen  = false;

  // ── Utility payments ──────────────────────────────────────────────────────
  billForm!:   FormGroup;
  billLoading  = false;
  billSuccess  = '';
  billError    = '';
  billFieldErr: Record<string, string> = {};

  selectedProvider: BillProvider = 'ENEO';

  providers: BillProviderConfig[] = [
    { id: 'ENEO',     label: 'ENEO',     icon: 'bolt',          color: '#F5A623' },
    { id: 'CAMWATER', label: 'CAMWATER', icon: 'water_drop',    color: '#4A9EDF' },
    { id: 'CANAL+',   label: 'CANAL+',   icon: 'tv',            color: '#CC0000' },
    { id: 'CAMTEL',   label: 'CAMTEL',   icon: 'language',      color: '#00A36C' },
  ];

  // ── Airtime ───────────────────────────────────────────────────────────────
  airtimeForm!:   FormGroup;
  airtimeLoading  = false;
  airtimeSuccess  = '';
  airtimeError    = '';
  airtimeFieldErr: Record<string, string> = {};

  selectedNetwork: 'mtn' | 'orange' = 'mtn';

  // ── Recent payments history ───────────────────────────────────────────────
  recentPayments: Transaction[] = [];
  loadingHistory  = true;

  // ── Beneficiaries ─────────────────────────────────────────────────────────
  billBeneficiaries:    Beneficiary[] = [];
  airtimeBeneficiaries: Beneficiary[] = [];
  saveBillFlash    = '';
  saveAirtimeFlash = '';

  // Inline "save beneficiary" prompts (one-click)
  saveBillPromptOpen    = false;
  saveAirtimePromptOpen = false;
  saveBillName    = '';
  saveAirtimeName = '';
  saveLoading     = false;

  constructor(
    private fb:            FormBuilder,
    private txService:     TransactionService,
    private userService:   UserService,
    private bService:      BeneficiaryService,
    private notifications: NotificationService,
    private auth:          AuthService,
  ) {}

  ngOnInit(): void {
    this.billForm = this.fb.group({
      meter_number: ['', [Validators.required, Validators.minLength(3)]],
      amount:       ['', [Validators.required, Validators.min(100)]],
    });

    this.airtimeForm = this.fb.group({
      phone:  ['', [Validators.required, Validators.pattern(/^\+?237[0-9]{8,9}$/)]],
      amount: ['', [Validators.required, Validators.min(100)]],
    });

    this.userService.getProfile().subscribe({
      next: (u) => {
        this.user = u;
        if (u.phone_number) this.airtimeForm.patchValue({ phone: u.phone_number });
      },
    });

    this.loadHistory();
    this.loadBeneficiaries();
  }

  loadBeneficiaries(): void {
    this.bService.list('BILL_PAYMENT').subscribe({
      next: (list) => this.billBeneficiaries = list,
      error: () => { /* non-critical */ },
    });
    this.bService.list('AIRTIME').subscribe({
      next: (list) => this.airtimeBeneficiaries = list,
      error: () => { /* non-critical */ },
    });
  }

  pickBillBeneficiary(b: Beneficiary): void {
    if (b.provider) {
      const match = this.providers.find(p => p.id === b.provider);
      if (match) this.selectedProvider = match.id;
    }
    this.billForm.patchValue({ meter_number: b.identifier });
  }

  pickAirtimeBeneficiary(b: Beneficiary): void {
    const network = (b.provider || '').toLowerCase();
    if (network === 'mtn' || network === 'orange') {
      this.selectedNetwork = network;
    }
    this.airtimeForm.patchValue({ phone: b.identifier });
  }

  /** Open the inline name-picker for the bill beneficiary. */
  openSaveBill(): void {
    const meter = this.billForm.value.meter_number;
    if (!meter) return;
    this.saveBillName       = `${this.selectedProvider} — ${meter}`;
    this.saveBillPromptOpen = true;
  }

  cancelSaveBill(): void {
    this.saveBillPromptOpen = false;
    this.saveBillName       = '';
  }

  confirmSaveBill(): void {
    const name  = this.saveBillName.trim();
    const meter = this.billForm.value.meter_number;
    if (!name || !meter || this.saveLoading) return;
    this.saveLoading = true;
    this.bService.create({
      name, identifier: meter,
      category: 'BILL_PAYMENT',
      provider: this.selectedProvider,
    }).subscribe({
      next: (b) => {
        this.saveLoading        = false;
        this.saveBillPromptOpen = false;
        this.billBeneficiaries  = [b, ...this.billBeneficiaries];
        this.saveBillFlash      = 'Saved!';
        setTimeout(() => this.saveBillFlash = '', 2500);
      },
      error: () => {
        this.saveLoading   = false;
        this.saveBillFlash = 'Could not save.';
      },
    });
  }

  /** Open the inline name-picker for the airtime beneficiary. */
  openSaveAirtime(): void {
    const phone = this.airtimeForm.value.phone;
    if (!phone) return;
    this.saveAirtimeName       = `${this.selectedNetwork.toUpperCase()} — ${phone}`;
    this.saveAirtimePromptOpen = true;
  }

  cancelSaveAirtime(): void {
    this.saveAirtimePromptOpen = false;
    this.saveAirtimeName       = '';
  }

  confirmSaveAirtime(): void {
    const name  = this.saveAirtimeName.trim();
    const phone = this.airtimeForm.value.phone;
    if (!name || !phone || this.saveLoading) return;
    this.saveLoading = true;
    this.bService.create({
      name, identifier: phone,
      category: 'AIRTIME',
      provider: this.selectedNetwork.toUpperCase(),
    }).subscribe({
      next: (b) => {
        this.saveLoading           = false;
        this.saveAirtimePromptOpen = false;
        this.airtimeBeneficiaries  = [b, ...this.airtimeBeneficiaries];
        this.saveAirtimeFlash      = 'Saved!';
        setTimeout(() => this.saveAirtimeFlash = '', 2500);
      },
      error: () => {
        this.saveLoading      = false;
        this.saveAirtimeFlash = 'Could not save.';
      },
    });
  }

  // ── Utility payment ───────────────────────────────────────────────────────
  get bf() { return this.billForm.controls; }

  selectProvider(id: BillProvider): void { this.selectedProvider = id; }

  submitBill(): void {
    if (this.billForm.invalid || this.billLoading) return;
    this.billLoading  = true;
    this.billSuccess  = '';
    this.billError    = '';
    this.billFieldErr = {};

    this.txService.payBill({
      provider:     this.selectedProvider,
      meter_number: this.billForm.value.meter_number,
      amount:       this.billForm.value.amount,
    }).subscribe({
      next: (txn) => {
        this.billLoading = false;
        const prov = this.providers.find(p => p.id === this.selectedProvider)!;
        this.billSuccess = `${prov.label} payment of ${Number(txn.amount).toLocaleString('fr-CM')} XAF was successful!`;
        this.billForm.reset();
        this.userService.getProfile().subscribe({ next: (u) => this.user = u });
        this.loadHistory();
        this.notifications.refresh();
        setTimeout(() => this.billSuccess = '', 6000);
      },
      error: (err: HttpErrorResponse) => {
        this.billLoading = false;
        this.parseErrors(err, 'bill');
      },
    });
  }

  // ── Airtime ───────────────────────────────────────────────────────────────
  get af() { return this.airtimeForm.controls; }

  selectNetwork(n: 'mtn' | 'orange'): void { this.selectedNetwork = n; }

  submitAirtime(): void {
    if (this.airtimeForm.invalid || this.airtimeLoading) return;
    this.airtimeLoading  = true;
    this.airtimeSuccess  = '';
    this.airtimeError    = '';
    this.airtimeFieldErr = {};

    this.txService.purchaseAirtime({
      network: this.selectedNetwork,
      phone:   this.airtimeForm.value.phone,
      amount:  this.airtimeForm.value.amount,
    }).subscribe({
      next: (txn) => {
        this.airtimeLoading = false;
        const label = this.selectedNetwork === 'mtn' ? 'MTN' : 'Orange';
        this.airtimeSuccess = `${label} airtime of ${Number(txn.amount).toLocaleString('fr-CM')} XAF sent successfully!`;
        this.airtimeForm.patchValue({ amount: '' });
        this.userService.getProfile().subscribe({ next: (u) => this.user = u });
        this.loadHistory();
        this.notifications.refresh();
        setTimeout(() => this.airtimeSuccess = '', 6000);
      },
      error: (err: HttpErrorResponse) => {
        this.airtimeLoading = false;
        this.parseErrors(err, 'airtime');
      },
    });
  }

  // ── History ───────────────────────────────────────────────────────────────
  loadHistory(): void {
    this.loadingHistory = true;
    this.txService.getAll().subscribe({
      next: (all) => {
        this.recentPayments = all
          .filter(t => t.transaction_type === 'BILL_PAYMENT' || t.transaction_type === 'AIRTIME')
          .slice(0, 5);
        this.loadingHistory = false;
      },
      error: () => { this.loadingHistory = false; },
    });
  }

  paymentIcon(tx: Transaction): string {
    if (tx.transaction_type === 'AIRTIME') return 'smartphone';
    const desc = (tx.description || '').toUpperCase();
    if (desc.startsWith('ENEO'))     return 'bolt';
    if (desc.startsWith('CAMWATER')) return 'water_drop';
    if (desc.startsWith('CANAL'))    return 'tv';
    if (desc.startsWith('CAMTEL'))   return 'language';
    return 'receipt_long';
  }

  paymentColor(tx: Transaction): string {
    if (tx.transaction_type === 'AIRTIME') {
      return tx.description?.includes('MTN') ? '#FFC300' : '#FF6B1A';
    }
    const desc = (tx.description || '').toUpperCase();
    if (desc.startsWith('ENEO'))     return '#F5A623';
    if (desc.startsWith('CAMWATER')) return '#4A9EDF';
    if (desc.startsWith('CANAL'))    return '#CC0000';
    if (desc.startsWith('CAMTEL'))   return '#00A36C';
    return '#D4AF37';
  }

  hexToRgb(hex: string): string {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return `${r}, ${g}, ${b}`;
  }

  toggleSidebar(): void { this.sidebarOpen = !this.sidebarOpen; }
  closeSidebar():  void { this.sidebarOpen = false; }
  logout():        void { this.auth.logout(); }

  private parseErrors(err: HttpErrorResponse, target: 'bill' | 'airtime'): void {
    const setErr  = (msg: string) => target === 'bill' ? this.billError    = msg  : this.airtimeError    = msg;
    const setFErr = (k: string, v: string) => {
      if (target === 'bill') this.billFieldErr[k] = v;
      else                   this.airtimeFieldErr[k] = v;
    };

    if (!err.error)             { setErr('An unexpected error occurred.'); return; }
    if (err.error.detail)       { setErr(err.error.detail); return; }
    if (typeof err.error === 'string') { setErr(err.error); return; }

    const general: string[] = [];
    for (const key of Object.keys(err.error)) {
      const msg = Array.isArray(err.error[key]) ? err.error[key].join(' ') : String(err.error[key]);
      const knownFields = target === 'bill'
        ? ['provider', 'meter_number', 'amount']
        : ['network', 'phone', 'amount'];
      if (knownFields.includes(key)) setFErr(key, msg);
      else general.push(msg);
    }
    if (general.length) setErr(general.join(' | '));
  }
}
