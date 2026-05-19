import {
  Component, OnInit, OnDestroy, HostListener,
  ElementRef, ViewChild,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterLink } from '@angular/router';
import { Subscription } from 'rxjs';
import { NotificationService } from '../../services/notification.service';
import { TPipe } from '../../pipes/t.pipe';
import { AppNotification, NotificationCategory } from '../../models/transaction.model';

@Component({
  selector: 'app-notif-bell',
  standalone: true,
  imports: [CommonModule, RouterLink, TPipe],
  templateUrl: './notif-bell.html',
  styleUrl:    './notif-bell.scss',
})
export class NotifBell implements OnInit, OnDestroy {

  open  = false;
  /** Top 8 notifications, sourced from the shared service stream. */
  items: AppNotification[] = [];
  unreadCount = 0;

  /** Inline style for the dropdown — set from the bell's viewport rect so the
   *  dropdown can float above ANY page's overflow:hidden ancestors. */
  dropdownStyle: { top: string; right: string } = { top: '0px', right: '0px' };

  @ViewChild('bellBtn', { static: true }) bellBtn!: ElementRef<HTMLButtonElement>;

  private subs: Subscription[] = [];

  constructor(
    private notifications: NotificationService,
    private router:        Router,
    private host:          ElementRef,
  ) {}

  ngOnInit(): void {
    this.notifications.startPolling();
    this.subs.push(
      this.notifications.unreadCount$.subscribe(c => this.unreadCount = c),
      this.notifications.notifications$.subscribe(list => this.items = list.slice(0, 8)),
    );
  }

  ngOnDestroy(): void {
    this.subs.forEach(s => s.unsubscribe());
  }

  toggle(event: Event): void {
    event.stopPropagation();
    this.open = !this.open;
    if (this.open) {
      this.positionDropdown();
      this.notifications.refresh();
    }
  }

  /** Compute viewport coordinates so position:fixed escapes any parent
   *  overflow:hidden / clip-path. Right-aligned to the bell button. */
  private positionDropdown(): void {
    const rect = this.bellBtn.nativeElement.getBoundingClientRect();
    const viewportW = window.innerWidth;
    // Mobile: full-width-ish (16px gutter); Desktop: right-aligned to bell.
    if (viewportW < 480) {
      this.dropdownStyle = {
        top:   `${rect.bottom + 8}px`,
        right: `8px`,
      };
    } else {
      this.dropdownStyle = {
        top:   `${rect.bottom + 10}px`,
        right: `${Math.max(8, viewportW - rect.right)}px`,
      };
    }
  }

  click(n: AppNotification): void {
    if (!n.read) this.notifications.markRead(n.id).subscribe({ error: () => {} });
    if (n.action_url) this.router.navigateByUrl(n.action_url).catch(() => {});
    this.open = false;
  }

  markAllRead(event: Event): void {
    event.stopPropagation();
    this.notifications.markAllRead().subscribe({ error: () => {} });
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

  @HostListener('document:click', ['$event'])
  onDocClick(event: Event): void {
    if (this.open && !this.host.nativeElement.contains(event.target)) {
      // The dropdown is in document.body via position:fixed so we also need
      // to verify the click didn't land on it.
      const target = event.target as Node;
      const dd = document.querySelector('.bell-dropdown');
      if (dd && dd.contains(target)) return;
      this.open = false;
    }
  }

  @HostListener('window:resize')
  onResize(): void {
    if (this.open) this.positionDropdown();
  }

  @HostListener('window:scroll')
  onScroll(): void {
    if (this.open) this.positionDropdown();
  }
}
