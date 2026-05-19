import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { ReactiveFormsModule, FormBuilder, FormGroup, Validators } from '@angular/forms';
import { HttpErrorResponse } from '@angular/common/http';
import { AuthService } from '../../services/auth.service';

@Component({
  selector: 'app-forgot-password',
  standalone: true,
  imports: [CommonModule, RouterLink, ReactiveFormsModule],
  templateUrl: './forgot-password.html',
  styleUrl:    './forgot-password.scss',
})
export class ForgotPassword implements OnInit {

  form!: FormGroup;
  loading = false;
  /** Set after the API call succeeds (always 200, regardless of email). */
  submitted = false;
  errorMessage = '';

  constructor(
    private fb:   FormBuilder,
    private auth: AuthService,
  ) {}

  ngOnInit(): void {
    this.form = this.fb.group({
      email: ['', [Validators.required, Validators.email]],
    });
  }

  get f() { return this.form.controls; }

  submit(): void {
    if (this.form.invalid || this.loading) return;
    this.loading      = true;
    this.errorMessage = '';

    this.auth.requestPasswordReset(this.form.value.email).subscribe({
      next: () => {
        this.loading   = false;
        this.submitted = true;
      },
      error: (err: HttpErrorResponse) => {
        this.loading      = false;
        this.errorMessage = err.error?.detail || 'Something went wrong. Please try again.';
      },
    });
  }
}
