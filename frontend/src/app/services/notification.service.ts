import { Injectable, OnDestroy } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { BehaviorSubject, Observable, Subscription, interval, tap } from 'rxjs';
import { environment } from '../../environments/environment';
import { AppNotification, NotificationListResponse } from '../models/transaction.model';

/**
 * Single source of truth for in-app notifications.
 *
 * Every `<app-notif-bell>` and the dedicated /notifications page subscribe to
 * the same streams here, so changes (mark-read, new arrivals) are reflected
 * on every page instantly.
 *
 * Polls the API every 30 seconds while a user is logged in.
 */
@Injectable({ providedIn: 'root' })
export class NotificationService implements OnDestroy {

  private api = environment.apiUrl;

  private _unreadCount = new BehaviorSubject<number>(0);
  unreadCount$ = this._unreadCount.asObservable();
  get unreadCount(): number { return this._unreadCount.value; }

  private _notifications = new BehaviorSubject<AppNotification[]>([]);
  notifications$ = this._notifications.asObservable();
  get notifications(): AppNotification[] { return this._notifications.value; }

  /** Polling interval in ms. 30 seconds keeps the badge fresh without spamming. */
  private static readonly POLL_INTERVAL_MS = 30_000;
  /** How many notifications to pull on each refresh. */
  private static readonly DEFAULT_LIMIT = 20;

  private pollSub?: Subscription;
  private started = false;

  constructor(private http: HttpClient) {}

  /**
   * Start background polling. Safe to call multiple times — only the first call
   * has effect. Called automatically by the bell component on first construction.
   */
  startPolling(): void {
    if (this.started) return;
    this.started = true;

    // Immediate fetch so the first page render has fresh data.
    this.fetch({ limit: NotificationService.DEFAULT_LIMIT }).subscribe({ error: () => {} });

    // Then poll every N seconds.
    this.pollSub = interval(NotificationService.POLL_INTERVAL_MS).subscribe(() => {
      this.fetch({ limit: NotificationService.DEFAULT_LIMIT }).subscribe({ error: () => {} });
    });
  }

  stopPolling(): void {
    this.pollSub?.unsubscribe();
    this.pollSub = undefined;
    this.started = false;
    this._notifications.next([]);
    this._unreadCount.next(0);
  }

  ngOnDestroy(): void {
    this.stopPolling();
  }

  /** Manually trigger a refresh — useful right after a successful transaction. */
  refresh(): void {
    this.fetch({ limit: NotificationService.DEFAULT_LIMIT }).subscribe({ error: () => {} });
  }

  /** Raw fetch (also updates the shared streams). */
  fetch(opts?: { unread?: boolean; limit?: number }): Observable<NotificationListResponse> {
    let params = new HttpParams();
    if (opts?.unread) params = params.set('unread', '1');
    if (opts?.limit)  params = params.set('limit', String(opts.limit));
    return this.http
      .get<NotificationListResponse>(`${this.api}/api/auth/notifications/`, { params })
      .pipe(tap(res => {
        this._unreadCount.next(res.unread_count);
        this._notifications.next(res.results);
      }));
  }

  markRead(id: string): Observable<AppNotification> {
    return this.http
      .post<AppNotification>(`${this.api}/api/auth/notifications/${id}/read/`, {})
      .pipe(tap(() => {
        const wasUnread = this._notifications.value.find(n => n.id === id && !n.read);
        const list = this._notifications.value.map(n =>
          n.id === id ? { ...n, read: true } : n
        );
        this._notifications.next(list);
        if (wasUnread) {
          this._unreadCount.next(Math.max(0, this._unreadCount.value - 1));
        }
      }));
  }

  markAllRead(): Observable<{ detail: string }> {
    return this.http
      .post<{ detail: string }>(`${this.api}/api/auth/notifications/mark-all-read/`, {})
      .pipe(tap(() => {
        const list = this._notifications.value.map(n => ({ ...n, read: true }));
        this._notifications.next(list);
        this._unreadCount.next(0);
      }));
  }

  delete(id: string): Observable<void> {
    return this.http
      .delete<void>(`${this.api}/api/auth/notifications/${id}/delete/`)
      .pipe(tap(() => {
        const removed = this._notifications.value.find(n => n.id === id);
        this._notifications.next(this._notifications.value.filter(n => n.id !== id));
        if (removed && !removed.read) {
          this._unreadCount.next(Math.max(0, this._unreadCount.value - 1));
        }
      }));
  }
}
