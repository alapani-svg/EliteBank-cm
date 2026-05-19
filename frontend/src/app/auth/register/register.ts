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

  registerForm!: FormGroup;
  isLoading    = false;
  serverError  = '';
  showPw       = false;
  showPwC      = false;

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
  }

  get f() { return this.registerForm.controls; }
  get mismatch(): boolean {
    return this.registerForm.hasError('passwordMismatch') &&
           (this.f['password_confirm'].dirty || this.f['password_confirm'].touched);
  }

  togglePw():  void { this.showPw  = !this.showPw;  }
  togglePwC(): void { this.showPwC = !this.showPwC; }

  onSubmit(): void {
    if (this.registerForm.invalid || this.isLoading) return;
    this.isLoading   = true;
    this.serverError = '';

    this.auth.register(this.registerForm.value).subscribe({
      next: () => {
        this.isLoading = false;
        this.router.navigate(['/dashboard']);
      },
      error: (err: HttpErrorResponse) => {
        this.isLoading   = false;
        this.serverError = this.parseError(err);
      }
    });
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
