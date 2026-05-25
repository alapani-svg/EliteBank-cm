import { Component, OnInit } from '@angular/core';
import { RouterLink, Router } from '@angular/router';
import {
  ReactiveFormsModule, FormBuilder, FormGroup,
  Validators, AbstractControl, ValidationErrors
} from '@angular/forms';
import { CommonModule } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { AuthService } from '../../services/auth.service';

// Custom cross-field validator: password === password_confirm
function passwordMatch(group: AbstractControl): ValidationErrors | null {
  const pw  = group.get('password')?.value;
  const cpw = group.get('password_confirm')?.value;
  return pw === cpw ? null : { passwordMismatch: true };
}

@Component({
  selector: 'app-register',
  standalone: true,
  imports: [RouterLink, ReactiveFormsModule, CommonModule],
  templateUrl: './register.html',
  styleUrl: './register.scss',
})
export class Register implements OnInit {

  // ── Step 1: signup form ───────────────────────────────────────────────────
  registerForm!: FormGroup;
  isLoading    = false;
  serverError  = '';
  showPw       = false;
  showPwC      = false;

  // ── Step 2: OTP verification panel ────────────────────────────────────────
  /** When non-empty, the OTP panel is shown instead of the signup form. */
  challengeId    = '';
  maskedEmail    = '';
  registeredEmail = '';
  otpForm!: FormGroup;
  otpLoading = false;
  otpError   = '';
  resendCooldown = 0;
  private resendTimer?: ReturnType<typeof setInterval>;

  // ── Step 3: done ──────────────────────────────────────────────────────────
  verified = false;

  constructor(
    private fb: FormBuilder,
    private auth: AuthService,
    private router: Router
  ) {}

  ngOnInit(): void {
    this.registerForm = this.fb.group(
      {
        full_name:        ['', [Validators.required, Validators.minLength(3)]],
        email:            ['', [Validators.required, Validators.email]],
        phone_number:     ['', [Validators.required, Validators.pattern(/^\+?[\d\s\-]{9,15}$/)]],
        password:         ['', [Validators.required, Validators.minLength(8),
                                Validators.pattern(/(?=.*[a-zA-Z])(?=.*\d).{8,}/)]],
        password_confirm: ['', Validators.required],
      },
      { validators: passwordMatch }
    );

    this.otpForm = this.fb.group({
      code: ['', [Validators.required, Validators.pattern(/^\d{6}$/)]],
    });
  }

  get f()  { return this.registerForm.controls; }
  get of() { return this.otpForm.controls; }
  get mismatch(): boolean {
    return this.registerForm.hasError('passwordMismatch') &&
           (this.f['password_confirm'].dirty || this.f['password_confirm'].touched);
  }

  togglePw():  void { this.showPw  = !this.showPw;  }
  togglePwC(): void { this.showPwC = !this.showPwC; }

  // ── Step 1: submit signup ─────────────────────────────────────────────────
  onSubmit(): void {
    if (this.registerForm.invalid || this.isLoading) return;
    this.isLoading   = true;
    this.serverError = '';

    this.auth.register(this.registerForm.value).subscribe({
      next: (res) => {
        this.isLoading       = false;
        this.challengeId     = res.challenge_id;
        this.maskedEmail     = res.masked_email;
        this.registeredEmail = res.email;
        this.startResendCooldown(30);
      },
      error: (err: HttpErrorResponse) => {
        this.isLoading   = false;
        this.serverError = this.parseError(err);
      }
    });
  }

  // ── Step 2: verify OTP ────────────────────────────────────────────────────
  verifyOtp(): void {
    if (this.otpForm.invalid || this.otpLoading) return;
    this.otpLoading = true;
    this.otpError   = '';

    this.auth.verifyRegistration(this.challengeId, this.otpForm.value.code).subscribe({
      next: () => {
        this.otpLoading = false;
        this.stopResendCooldown();
        this.verified = true;
        // Auto-redirect to /login after 2.5 s
        setTimeout(() => this.router.navigate(['/login']), 2500);
      },
      error: (err: HttpErrorResponse) => {
        this.otpLoading = false;
        this.otpError   = this.parseError(err);
        this.otpForm.patchValue({ code: '' });
      },
    });
  }

  resendOtp(): void {
    if (this.resendCooldown > 0 || this.otpLoading) return;
    this.otpError = '';
    this.auth.resendRegistrationOtp(this.registeredEmail).subscribe({
      next: (res) => {
        if (res.challenge_id) this.challengeId = res.challenge_id;
        if (res.masked_email) this.maskedEmail = res.masked_email;
        this.startResendCooldown(30);
      },
      error: (err: HttpErrorResponse) => {
        this.otpError = this.parseError(err);
      },
    });
  }

  cancelOtp(): void {
    this.challengeId      = '';
    this.maskedEmail      = '';
    this.registeredEmail  = '';
    this.otpForm.reset();
    this.stopResendCooldown();
  }

  private startResendCooldown(seconds: number): void {
    this.stopResendCooldown();
    this.resendCooldown = seconds;
    this.resendTimer = setInterval(() => {
      this.resendCooldown--;
      if (this.resendCooldown <= 0) this.stopResendCooldown();
    }, 1000);
  }

  private stopResendCooldown(): void {
    if (this.resendTimer) { clearInterval(this.resendTimer); this.resendTimer = undefined; }
    this.resendCooldown = 0;
  }

  private parseError(err: HttpErrorResponse): string {
    if (!err.error) return 'An unexpected error occurred.';
    if (err.error.detail) return err.error.detail;
    if (typeof err.error === 'string') return err.error;
    const msgs: string[] = [];
    for (const k of Object.keys(err.error)) {
      const v = err.error[k];
      msgs.push(`${k.replace(/_/g,' ')}: ${Array.isArray(v) ? v.join(', ') : v}`);
    }
    return msgs.join(' | ') || 'Registration failed. Please check your details.';
  }
}
