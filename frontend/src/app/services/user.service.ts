import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { BehaviorSubject, Observable, tap } from 'rxjs';
import { environment } from '../../environments/environment';
import { User, ProfileUpdatePayload, ChangePasswordPayload } from '../models/user.model';
import { LanguageService } from './language.service';

@Injectable({ providedIn: 'root' })
export class UserService {

  private api = environment.apiUrl;

  /** Shared current user — populated by getProfile() and updated by mutations.
   *  Components subscribe instead of fetching the profile independently. */
  private _currentUser = new BehaviorSubject<User | null>(null);
  currentUser$ = this._currentUser.asObservable();
  get currentUser(): User | null { return this._currentUser.value; }

  constructor(
    private http: HttpClient,
    private language: LanguageService,
  ) {
    // Whenever the user record changes, sync the UI language to match the
    // user's stored preference. This handles login, profile refresh, and
    // language updates triggered from elsewhere.
    this.currentUser$.subscribe(user => {
      if (user?.language) this.language.use(user.language);
    });
  }

  /** Fetch the profile from the API and broadcast it. */
  getProfile(): Observable<User> {
    return this.http.get<User>(`${this.api}/api/auth/me/`).pipe(
      tap(user => this._currentUser.next(user)),
    );
  }

  /** Ensure currentUser$ has a value. Fetches only if cache is empty. */
  ensureLoaded(): void {
    if (!this._currentUser.value) this.getProfile().subscribe();
  }

  /** Manually patch the cached user (e.g. after avatar upload). */
  setUser(user: User): void {
    this._currentUser.next(user);
  }

  updateProfile(payload: ProfileUpdatePayload): Observable<{ message: string; user: User }> {
    return this.http
      .patch<{ message: string; user: User }>(`${this.api}/api/auth/me/`, payload)
      .pipe(tap(res => this._currentUser.next(res.user)));
  }

  changePassword(payload: ChangePasswordPayload): Observable<{ message: string }> {
    return this.http.post<{ message: string }>(`${this.api}/api/auth/change-password/`, payload);
  }

  toggle2FA(enabled: boolean): Observable<{ message: string; two_factor_enabled: boolean }> {
    return this.http.post<{ message: string; two_factor_enabled: boolean }>(
      `${this.api}/api/auth/2fa/`, { enabled }
    );
  }

  uploadAvatar(file: File): Observable<{ message: string; avatar_url: string }> {
    const formData = new FormData();
    formData.append('avatar', file);
    return this.http
      .post<{ message: string; avatar_url: string }>(`${this.api}/api/auth/avatar/`, formData)
      .pipe(tap(res => {
        const current = this._currentUser.value;
        if (current) this._currentUser.next({ ...current, avatar_url: res.avatar_url });
      }));
  }
}
