import { Component } from '@angular/core';
import { Hero } from '../../components/hero/hero';
import { Features } from '../../components/features/features';
import { Cta } from '../../components/cta/cta';
import { Navbar } from '../../components/navbar/navbar';
import { Footer } from '../../components/footer/footer';

@Component({
  selector: 'app-home',
  standalone: true,
  imports: [Navbar, Hero, Features, Cta, Footer],
  template: `
    <app-navbar></app-navbar>
    <app-hero></app-hero>
    <app-features></app-features>
    <app-cta></app-cta>
    <app-footer></app-footer>
  `
})
export class Home { }