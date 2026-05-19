import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import {
  ReactiveFormsModule, FormBuilder, FormGroup, Validators,
  AbstractControl, ValidationErrors,
} from '@angular/forms';
import { HttpErrorResponse } from '@angular/common/http';
import { AuthService } from '../../services/auth.service';

function passwordsMatch(g: AbstractControl): ValidationErrors | null {
  const a = g.get('new_password')?.value;
  const b = g.get('confirm_password')?.value;
  return a === b ? null : { mismatch: true };
}

@Component({
  selector: 'app-reset-password',
  standalone: true,
  imports: [CommonModule, RouterLink, ReactiveFormsModule],
  templateUrl: './reset-password.html',
  styleUrl:    './reset-password.scss',
})
export class ResetPassword implements OnInit {

  form!: FormGroup;
  token = '';
  loading = false;
  done    = false;
  error   = '';
  showPw  = false;
  showConfirmPw = false;

  constructor(
    private fb:     FormBuilder,
    private auth:   AuthService,
    private route:  ActivatedRoute,
    private router: Router,
  ) {}

  ngOnInit(): void {
    this.token = this.route.snapshot.queryParamMap.get('token') || '';
    this.form  = this.fb.group({
      new_password:     ['', [
        Validators.required,
        Validators.minLength(8),
        Validators.pattern(/(?=.*[a-zA-Z])(?=.*\d).{8,}/),
      ]],
      confirm_password: ['', Validators.required],
    }, { validators: passwordsMatch });
  }

  get f() { return this.form.controls; }

  get pwMismatch(): boolean {
    return this.form.hasError('mismatch') &&
      (this.f['confirm_password'].dirty || this.f['confirm_password'].touched);
  }

  submit(): void {
    if (this.form.invalid || this.loading) return;
    if (!this.token) {
      this.error = 'This reset link is missing its token. Please request a new one.';
      return;
    }

    this.loading = true;
    this.error   = '';

    this.auth.confirmPasswordReset(
      this.token,
      this.form.value.new_password,
      this.form.value.confirm_password,
    ).subscribe({
      next: () => {
        this.loading = false;
        this.done    = true;
        // Auto-redirect to /login after 3 seconds.
        setTimeout(() => this.router.navigate(['/login']), 3000);
      },
      error: (err: HttpErrorResponse) => {
        this.loading = false;
        this.error   = err.error?.detail
          || err.error?.new_password?.[0]
          || err.error?.confirm_password?.[0]
          || 'Could not reset your password. Please try again.';
      },
    });
  }
}
