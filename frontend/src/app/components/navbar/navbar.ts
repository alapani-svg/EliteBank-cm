import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-navbar',
  imports: [CommonModule, RouterLink],
  templateUrl: './navbar.html',
  styleUrl: './navbar.scss',
})
export class Navbar {
  mobileOpen = false;

  toggleMobile(): void { this.mobileOpen = !this.mobileOpen; }
  closeMobile():  void { this.mobileOpen = false; }
}
