import { Routes } from '@angular/router';
import { HomePageComponent } from './features/home/home-page/home-page';
import { NewsDetailsPageComponent } from './features/news/news-details-page/news-details-page';
import { AuthCard } from './shared/components/auth-card/auth-card';

export const appRoutes: Routes = [
  {
    path: '',
    component: HomePageComponent
  },
  {
    path: 'details/:id',
    component: NewsDetailsPageComponent
  },
  {
    path: 'login', 
    component: AuthCard //auth-card.ts => 33
  },
  {
    path: 'register',
    component: AuthCard
  },
  {
    path: '**',
    redirectTo: ''
  }

];