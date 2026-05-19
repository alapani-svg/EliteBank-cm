import { Component, OnInit, OnDestroy, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { Subscription } from 'rxjs';
import { UserService } from '../../services/user.service';
import { User } from '../../models/user.model';

@Component({
  selector: 'app-user-avatar',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './user-avatar.html',
  styleUrl:    './user-avatar.scss',
})
export class UserAvatar implements OnInit, OnDestroy {

  /** Size in pixels — defaults to 34 to match existing topbar slot. */
  @Input() size = 34;
  /** If true, clicking navigates to /profile. */
  @Input() clickable = true;

  user: User | null = null;
  private sub?: Subscription;

  constructor(private userService: UserService) {}

  ngOnInit(): void {
    this.sub = this.userService.currentUser$.subscribe(u => this.user = u);
    this.userService.ensureLoaded();
  }

  ngOnDestroy(): void {
    this.sub?.unsubscribe();
  }

  /** Two-letter initials from the user's full_name. */
  get initials(): string {
    if (!this.user?.full_name) return '';
    return this.user.full_name
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map(w => w[0].toUpperCase())
      .join('');
  }

  get sizePx(): string  { return `${this.size}px`; }
  get fontPx(): string  { return `${Math.round(this.size * 0.4)}px`; }
}
