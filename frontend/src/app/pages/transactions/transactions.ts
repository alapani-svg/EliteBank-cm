import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink, RouterLinkActive } from '@angular/router';
import { TransactionService } from '../../services/transaction.service';
import { AuthService } from '../../services/auth.service';
import { NotifBell } from '../../components/notif-bell/notif-bell';
import { UserAvatar } from '../../components/user-avatar/user-avatar';
import { TPipe } from '../../pipes/t.pipe';
import { Transaction } from '../../models/transaction.model';

@Component({
  selector: 'app-transactions',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink, RouterLinkActive, NotifBell, UserAvatar, TPipe],
  templateUrl: './transactions.html',
  styleUrl: './transactions.scss',
})
export class Transactions implements OnInit {

  transactions: Transaction[] = [];
  loading = true;
  error = '';
  sidebarOpen = false;

  activeFilter       = 'ALL';
  activeStatusFilter = 'ALL';

  filters       = ['ALL', 'TRANSFER', 'DEPOSIT', 'BILL_PAYMENT', 'AIRTIME', 'WITHDRAWAL'];
  statusFilters = ['ALL', 'COMPLETED', 'PENDING', 'FAILED'];

  // Statement download modal
  statementOpen = false;
  statementFrom = '';
  statementTo   = '';
  statementFormat: 'pdf' | 'csv' = 'pdf';
  downloadingStatement = false;
  statementError = '';

  constructor(
    private txService: TransactionService,
    private auth: AuthService,
  ) {}

  ngOnInit(): void {
    this.loadTransactions();
  }

  loadTransactions(): void {
    this.loading = true;
    this.error   = '';

    const type   = this.activeFilter       !== 'ALL' ? this.activeFilter       : undefined;
    const status = this.activeStatusFilter !== 'ALL' ? this.activeStatusFilter : undefined;

    this.txService.getAll({ type, status }).subscribe({
      next: (data) => {
        this.transactions = data;
        this.loading = false;
      },
      error: () => {
        this.error   = 'Failed to load transactions. Please try again.';
        this.loading = false;
      },
    });
  }

  applyFilter(type: string): void {
    this.activeFilter = type;
    this.loadTransactions();
  }

  applyStatusFilter(status: string): void {
    this.activeStatusFilter = status;
    this.loadTransactions();
  }

  isCredit(tx: Transaction): boolean {
    if (tx.transaction_type === 'DEPOSIT') return true;
    const userId = this.auth.getCurrentUserId();
    return tx.recipient === userId;
  }

  formatAmount(tx: Transaction): string {
    const sign = this.isCredit(tx) ? '+' : '-';
    return `${sign}${Number(tx.amount).toLocaleString('fr-CM')} XAF`;
  }

  // ── Statement download ────────────────────────────────────────────────────
  openStatement(): void {
    const today = new Date();
    const monthAgo = new Date();
    monthAgo.setDate(today.getDate() - 30);
    this.statementFrom = monthAgo.toISOString().slice(0, 10);
    this.statementTo   = today.toISOString().slice(0, 10);
    this.statementFormat = 'pdf';
    this.statementError = '';
    this.statementOpen = true;
  }

  closeStatement(): void {
    this.statementOpen = false;
    this.statementError = '';
  }

  downloadStatement(): void {
    if (this.downloadingStatement) return;
    if (!this.statementFrom || !this.statementTo) {
      this.statementError = 'Choose a from and to date.';
      return;
    }
    if (this.statementFrom > this.statementTo) {
      this.statementError = '`From` must be before `to`.';
      return;
    }
    this.downloadingStatement = true;
    this.statementError = '';
    this.txService.downloadStatement(
      this.statementFrom, this.statementTo, this.statementFormat,
    ).subscribe({
      next: (blob) => {
        this.downloadingStatement = false;
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `elite-statement-${this.statementFrom}_${this.statementTo}.${this.statementFormat}`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
        this.statementOpen = false;
      },
      error: () => {
        this.downloadingStatement = false;
        this.statementError = 'Could not generate statement. Please try again.';
      },
    });
  }

  toggleSidebar(): void { this.sidebarOpen = !this.sidebarOpen; }
  closeSidebar():  void { this.sidebarOpen = false; }
  logout():        void { this.auth.logout(); }
}
