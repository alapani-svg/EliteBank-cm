import { Component, OnInit, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink, RouterLinkActive } from '@angular/router';
import {
  ReactiveFormsModule, FormBuilder, FormGroup,
  Validators, AbstractControl, ValidationErrors
} from '@angular/forms';
import { HttpErrorResponse } from '@angular/common/http';
import { AuthService } from '../../services/auth.service';
import { UserService } from '../../services/user.service';
import { LanguageService } from '../../services/language.service';
import { NotifBell } from '../../components/notif-bell/notif-bell';
import { UserAvatar } from '../../components/user-avatar/user-avatar';
import { TPipe } from '../../pipes/t.pipe';
import { User } from '../../models/user.model';

function passwordMatch(g: AbstractControl): ValidationErrors | null {
  const pw  = g.get('new_password')?.value;
  const cpw = g.get('confirm_password')?.value;
  return pw === cpw ? null : { mismatch: true };
}

const LANG_LABELS: Record<string, string> = {
  en: 'English', fr: 'Français', es: 'Español', ar: 'العربية'
};

@Component({
  selector: 'app-profile',
  standalone: true,
  imports: [CommonModule, RouterLink, RouterLinkActive, ReactiveFormsModule, NotifBell, UserAvatar, TPipe],
  templateUrl: './profile.html',
  styleUrl: './profile.scss',
})
export class Profile implements OnInit {

  user: User | null = null;
  profileForm!: FormGroup;
  passwordForm!: FormGroup;

  profileLoading  = false;
  passwordLoading = false;
  avatarLoading   = false;
  loadingProfile  = true;

  profileSuccess = '';
  profileError   = '';
  passwordSuccess = '';
  passwordError  = '';
  avatarError    = '';
  avatarSuccess  = '';
  langSuccess    = '';

  showCurrentPw = false;
  showNewPw     = false;
  twoFactor     = false;
  emailNotif    = true;
  smsAlerts     = false;
  sidebarOpen   = false;
  helpOpen      = false;
  prefSavingEmail = false;
  prefSavingSms   = false;
  prefSavingLang  = false;
  prefFlash       = '';
  avatarPreview: string | null = null;

  private readonly MAX_SIZE = 10 * 1024 * 1024;

  constructor(
    private fb: FormBuilder,
    private auth: AuthService,
    private userService: UserService,
    private lang: LanguageService,
    private cdr: ChangeDetectorRef,
  ) {}

  ngOnInit(): void {
    this.profileForm = this.fb.group({
      full_name:    ['', [Validators.required, Validators.minLength(3)]],
      phone_number: ['', [Validators.required, Validators.pattern(/^\+?[\d\s\-]{9,15}$/)]],
      language:     ['en'],
    });

    this.passwordForm = this.fb.group({
      current_password: ['', Validators.required],
      new_password:     ['', [Validators.required, Validators.minLength(8),
                              Validators.pattern(/(?=.*[a-zA-Z])(?=.*\d).{8,}/)]],
      confirm_password: ['', Validators.required],
    }, { validators: passwordMatch });

    this.loadProfile();
  }

  loadProfile(): void {
    this.loadingProfile = true;
    this.userService.getProfile().subscribe({
      next: (user) => {
        this.user         = user;
        this.avatarPreview = null;
        this.twoFactor    = user.two_factor_enabled;
        this.emailNotif   = user.email_notifications;
        this.smsAlerts    = user.sms_alerts;
        this.loadingProfile = false;
        this.profileForm.patchValue({
          full_name:    user.full_name,
          phone_number: user.phone_number,
          language:     user.language || 'en',
        });
      },
      error: () => { this.loadingProfile = false; },
    });
  }

  onAvatarSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (!input.files?.length) return;

    const file = input.files[0];
    this.avatarError   = '';
    this.avatarSuccess = '';

    if (!file.type.startsWith('image/')) {
      this.avatarError = 'Please select an image file.';
      input.value = '';
      return;
    }
    if (file.size > this.MAX_SIZE) {
      this.avatarError = 'Image must be under 10MB.';
      input.value = '';
      return;
    }

    const reader = new FileReader();
    reader.onload = (e) => {
      this.avatarPreview = e.target?.result as string;
      this.cdr.detectChanges();
    };
    reader.readAsDataURL(file);

    this.avatarLoading = true;
    this.userService.uploadAvatar(file).subscribe({
      next: (res) => {
        this.avatarLoading = false;
        this.avatarSuccess = 'Profile picture updated!';
        if (this.user) this.user = { ...this.user, avatar_url: res.avatar_url };
        setTimeout(() => { this.avatarPreview = null; }, 0);
        input.value = '';
        setTimeout(() => this.avatarSuccess = '', 4000);
      },
      error: (err: HttpErrorResponse) => {
        this.avatarLoading = false;
        setTimeout(() => { this.avatarPreview = null; }, 0);
        this.avatarError   = err.error?.detail || 'Upload failed. Please try again.';
        input.value = '';
      },
    });
  }

  saveProfile(): void {
    if (this.profileForm.invalid || this.profileLoading) return;
    this.profileLoading = true;
    this.profileSuccess = '';
    this.profileError   = '';
    this.langSuccess    = '';

    const selectedLang = this.profileForm.value.language;
    const previousLang = this.user?.language;

    this.userService.updateProfile({
      full_name:           this.profileForm.value.full_name,
      phone_number:        this.profileForm.value.phone_number,
      language:            selectedLang,
      email_notifications: this.emailNotif,
      sms_alerts:          this.smsAlerts,
    }).subscribe({
      next: (res) => {
        this.profileLoading = false;
        this.profileSuccess = 'Profile updated successfully.';
        this.user = res.user;
        if (res.user.language !== previousLang) {
          this.langSuccess = `Language set to ${LANG_LABELS[selectedLang] || selectedLang}.`;
        }
        setTimeout(() => { this.profileSuccess = ''; this.langSuccess = ''; }, 4000);
      },
      error: (err: HttpErrorResponse) => {
        this.profileLoading = false;
        this.profileError   = this.parseError(err);
      },
    });
  }

  changePassword(): void {
    if (this.passwordForm.invalid || this.passwordLoading) return;
    this.passwordLoading = true;
    this.passwordSuccess = '';
    this.passwordError   = '';

    this.userService.changePassword(this.passwordForm.value).subscribe({
      next: () => {
        this.passwordLoading = false;
        this.passwordSuccess = 'Password changed successfully.';
        this.passwordForm.reset();
        setTimeout(() => this.passwordSuccess = '', 4000);
      },
      error: (err: HttpErrorResponse) => {
        this.passwordLoading = false;
        this.passwordError   = this.parseError(err);
      },
    });
  }

  toggle2FA(): void {
    this.twoFactor = !this.twoFactor;
    this.userService.toggle2FA(this.twoFactor).subscribe({
      next: () => this.flashPref(this.twoFactor ? '2FA enabled.' : '2FA disabled.'),
      error: () => { this.twoFactor = !this.twoFactor; this.flashPref('Could not update 2FA.', true); },
    });
  }

  /** Auto-save the email-notifications preference on toggle. */
  toggleEmailNotif(): void {
    const previous = this.emailNotif;
    this.emailNotif = !this.emailNotif;
    this.prefSavingEmail = true;
    this.userService.updateProfile({ email_notifications: this.emailNotif }).subscribe({
      next: () => {
        this.prefSavingEmail = false;
        this.flashPref(this.emailNotif ? 'Email alerts on.' : 'Email alerts off.');
      },
      error: () => {
        this.prefSavingEmail = false;
        this.emailNotif = previous;
        this.flashPref('Could not save email preference.', true);
      },
    });
  }

  /** Auto-save the SMS-alerts preference on toggle. */
  toggleSmsAlerts(): void {
    const previous = this.smsAlerts;
    this.smsAlerts = !this.smsAlerts;
    this.prefSavingSms = true;
    this.userService.updateProfile({ sms_alerts: this.smsAlerts }).subscribe({
      next: () => {
        this.prefSavingSms = false;
        this.flashPref(this.smsAlerts ? 'SMS alerts on.' : 'SMS alerts off.');
      },
      error: () => {
        this.prefSavingSms = false;
        this.smsAlerts = previous;
        this.flashPref('Could not save SMS preference.', true);
      },
    });
  }

  /** Auto-save the language preference when the dropdown changes.
   *  Switches the UI language immediately (optimistic) so the user sees the
   *  effect right away; rolls back if the API call fails. */
  onLanguageChange(): void {
    const lang = this.profileForm.value.language;
    if (!lang) return;
    const previous = this.lang.currentLang;
    this.lang.use(lang);  // optimistic UI flip
    this.prefSavingLang = true;
    this.userService.updateProfile({ language: lang }).subscribe({
      next: (res) => {
        this.prefSavingLang = false;
        this.user = res.user;
        this.flashPref(`${this.langLabel(lang)}.`);
      },
      error: () => {
        this.prefSavingLang = false;
        this.lang.use(previous);  // rollback
        this.profileForm.patchValue({ language: previous }, { emitEvent: false });
        this.flashPref('Could not change language.', true);
      },
    });
  }

  private langLabel(code: string): string {
    return LANG_LABELS[code] || code;
  }

  private flashPref(msg: string, _err = false): void {
    this.prefFlash = msg;
    setTimeout(() => { this.prefFlash = ''; }, 3000);
  }

  openHelp():  void { this.helpOpen = true; }
  closeHelp(): void { this.helpOpen = false; }

  toggleSidebar(): void { this.sidebarOpen = !this.sidebarOpen; }
  closeSidebar():  void { this.sidebarOpen = false; }
  logout():        void { this.auth.logout(); }

  get f()  { return this.profileForm.controls; }
  get pf() { return this.passwordForm.controls; }

  get pwMismatch(): boolean {
    return this.passwordForm.hasError('mismatch') &&
      (this.pf['confirm_password'].dirty || this.pf['confirm_password'].touched);
  }

  get displayAvatar(): string | null {
    return this.avatarPreview || this.user?.avatar_url || null;
  }

  private parseError(err: HttpErrorResponse): string {
    if (!err.error) return 'An unexpected error occurred.';
    if (err.error.detail) return err.error.detail;
    if (typeof err.error === 'string') return err.error;
    const msgs: string[] = [];
    for (const k of Object.keys(err.error)) {
      const v = err.error[k];
      msgs.push(`${k.replace(/_/g, ' ')}: ${Array.isArray(v) ? v.join(', ') : v}`);
    }
    return msgs.join(' | ') || 'Something went wrong.';
  }
}
