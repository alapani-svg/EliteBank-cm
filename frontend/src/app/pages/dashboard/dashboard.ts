import { Component, OnInit } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';
import { CommonModule } from '@angular/common';
import { AuthService } from '../../services/auth.service';
import { UserService } from '../../services/user.service';
import { TransactionService } from '../../services/transaction.service';
import { NotifBell } from '../../components/notif-bell/notif-bell';
import { UserAvatar } from '../../components/user-avatar/user-avatar';
import { TPipe } from '../../pipes/t.pipe';
import { User } from '../../models/user.model';
import { Transaction } from '../../models/transaction.model';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, RouterLink, RouterLinkActive, NotifBell, UserAvatar, TPipe],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.scss',
})
export class Dashboard implements OnInit {

  sidebarOpen = false;
  user: User | null = null;
  transactions: Transaction[] = [];
  loadingUser = true;
  loadingTx   = true;
  userId: string | null = null;

  constructor(
    private auth: AuthService,
    private userService: UserService,
    private txService: TransactionService,
  ) {}

  ngOnInit(): void {
    this.userId = this.auth.getCurrentUserId();

    this.userService.getProfile().subscribe({
      next:  (u) => { this.user = u; this.loadingUser = false; },
      error: ()  => { this.loadingUser = false; },
    });

    this.txService.getAll().subscribe({
      next:  (txs) => { this.transactions = txs.slice(0, 5); this.loadingTx = false; },
      error: ()    => { this.loadingTx = false; },
    });
  }

  isCredit(tx: Transaction): boolean {
    if (tx.transaction_type === 'DEPOSIT') return true;
    return tx.recipient === this.userId;
  }

  formatAmount(tx: Transaction): string {
    const sign = this.isCredit(tx) ? '+' : '-';
    return `${sign}${Number(tx.amount).toLocaleString('fr-CM')}`;
  }

  toggleSidebar(): void { this.sidebarOpen = !this.sidebarOpen; }
  closeSidebar():  void { this.sidebarOpen = false; }
  logout():        void { this.auth.logout(); }
}
