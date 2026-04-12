import { Component, inject, ChangeDetectorRef, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RegisterForm } from '../register-form/register-form';
import { InterestsForm } from '../interests-form/interests-form';
import { LoginForm } from '../login-form/login-form';
import { HttpClient } from '@angular/common/http';
import { ActivatedRoute, Router } from '@angular/router';

@Component({
  selector: 'app-auth-card',
  standalone: true,
  imports: [CommonModule, RegisterForm, InterestsForm, LoginForm],
  templateUrl: './auth-card.html',
  styleUrls: ['./auth-card.css']
})
export class AuthCard implements OnInit { 
  private http = inject(HttpClient); 
  private cdr = inject(ChangeDetectorRef);
  private router = inject(Router);
  private route = inject(ActivatedRoute);

  step = 1;
  mode: 'login' | 'signup' = 'login';
  registrationData: any = null;
  isLoading = false;
  errorMessage = '';
  successUser: any = null;
  returnUrl = '/';

  ngOnInit(): void {
    // Detect mode from route path
    const path = this.router.url;
    //apres login reussi : redirige vers la page detail 
    this.returnUrl = this.route.snapshot.queryParamMap.get('returnUrl') || '/';
    //auth-card.ts => 77

    if (path.includes('register')) {
      this.mode = 'signup';
    } else {
      this.mode = 'login';
    }
  }

  goToNextStep(data: any) {
    console.log("Registration data collected:", data);
    this.registrationData = data;
    this.step = 2;
    this.cdr.detectChanges();
  }

  finishSignup(interestIds: number[]) {
    if (!this.registrationData) return;

    this.isLoading = true;
    this.errorMessage = '';
    this.cdr.detectChanges();
    
    const payload = {
      ...this.registrationData,
      interest_ids: interestIds
    };

    this.http.post('http://127.0.0.1:8000/complete-signup', payload).subscribe({
      next: () => {
        this.isLoading = false;
        this.step = 3;
        console.log("Signup complete! Step set to 3.");
        this.cdr.detectChanges();
      },
      error: (err) => {
        this.isLoading = false;
        this.errorMessage = err.error?.detail || 'An error occurred during signup. Please try again.';
        console.error("Error completing signup:", err);
        this.cdr.detectChanges();
      }
    });
  }
  //sauvegarde currentUser dans localStorage puis navigateByUrl(returnUrl)
  onLoginSuccess(user: any) {
    this.successUser = user;
    localStorage.setItem('currentUser', JSON.stringify(user));
    this.router.navigateByUrl(this.returnUrl);
    //news-details-page.ts =< 136
  }

  switchToSignup() {
    this.router.navigate(['/register']);
    this.mode = 'signup';
    this.step = 1;
    this.errorMessage = '';
    this.cdr.detectChanges();
  }

  switchToLogin() {
    this.router.navigate(['/login']);
    this.mode = 'login';
    this.step = 1;
    this.errorMessage = '';
    this.cdr.detectChanges();
  }
}