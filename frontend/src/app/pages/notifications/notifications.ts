import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterLink, RouterLinkActive } from '@angular/router';
import { NotificationService } from '../../services/notification.service';
import { AuthService } from '../../services/auth.service';
import { NotifBell } from '../../components/notif-bell/notif-bell';
import { UserAvatar } from '../../components/user-avatar/user-avatar';
import { TPipe } from '../../pipes/t.pipe';
import { AppNotification, NotificationCategory } from '../../models/transaction.model';

@Component({
  selector: 'app-notifications',
  standalone: true,
  imports: [CommonModule, RouterLink, RouterLinkActive, NotifBell, UserAvatar, TPipe],
  templateUrl: './notifications.html',
  styleUrl:    './notifications.scss',
})
export class Notifications implements OnInit {

  items: AppNotification[] = [];
  unreadCount = 0;
  loading     = true;
  sidebarOpen = false;
  filter: 'ALL' | 'UNREAD' = 'ALL';

  constructor(
    private notifications: NotificationService,
    private auth:          AuthService,
    private router:        Router,
  ) {}

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading = true;
    this.notifications.fetch({ unread: this.filter === 'UNREAD', limit: 200 }).subscribe({
      next: (res) => {
        this.items = res.results;
        this.unreadCount = res.unread_count;
        this.loading = false;
      },
      error: () => { this.loading = false; },
    });
  }

  setFilter(f: 'ALL' | 'UNREAD'): void {
    this.filter = f;
    this.load();
  }

  click(n: AppNotification): void {
    if (!n.read) {
      this.notifications.markRead(n.id).subscribe({
        next: () => { n.read = true; this.unreadCount = Math.max(0, this.unreadCount - 1); },
      });
    }
    if (n.action_url) {
      // action_url is server-relative like /transactions/<uuid>/
      this.router.navigateByUrl(n.action_url).catch(() => {});
    }
  }

  markAllRead(): void {
    this.notifications.markAllRead().subscribe({
      next: () => {
        this.items.forEach(n => n.read = true);
        this.unreadCount = 0;
      },
    });
  }

  remove(n: AppNotification, event: Event): void {
    event.stopPropagation();
    this.notifications.delete(n.id).subscribe({
      next: () => {
        this.items = this.items.filter(x => x.id !== n.id);
        if (!n.read) this.unreadCount = Math.max(0, this.unreadCount - 1);
      },
    });
  }

  iconFor(c: NotificationCategory): string {
    switch (c) {
      case 'TRANSFER':     return 'send';
      case 'DEPOSIT':      return 'south_west';
      case 'WITHDRAWAL':   return 'arrow_circle_up';
      case 'BILL_PAYMENT': return 'receipt_long';
      case 'AIRTIME':      return 'smartphone';
      case 'SECURITY':     return 'shield';
      case 'ACCOUNT':      return 'person';
      default:             return 'notifications';
    }
  }

  toggleSidebar(): void { this.sidebarOpen = !this.sidebarOpen; }
  closeSidebar():  void { this.sidebarOpen = false; }
  logout():        void { this.auth.logout(); }
}
