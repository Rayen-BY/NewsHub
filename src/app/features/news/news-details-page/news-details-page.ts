import { DatePipe, NgFor, NgIf, TitleCasePipe } from '@angular/common';

import { Component, OnInit, inject } from '@angular/core';

import { ActivatedRoute, Router, RouterLink } from '@angular/router';

import { NewsCategory } from '../../../core/models/category.model';
import { NewsArticle } from '../../../core/models/news.model';

import { CommentsService, NewsComment } from '../../../core/services/comments';
import { FavoritesService } from '../../../core/services/favorites';
import { NewsService } from '../../../core/services/news';

import { HeaderComponent } from '../../../shared/components/header/header';

import { FormsModule } from '@angular/forms';

@Component({
  selector: 'app-news-details-page', 
  standalone: true, 
  imports: [DatePipe, FormsModule, HeaderComponent, NgFor, NgIf, RouterLink, TitleCasePipe], // dépendances utilisées dans HTML
  templateUrl: './news-details-page.html', 
  styleUrl: './news-details-page.css' 
})
export class NewsDetailsPageComponent implements OnInit {
  private static readonly LAST_VIEWED_ARTICLE_KEY = 'lastViewedArticle';
  private static readonly PENDING_SAVE_ACTION_KEY = 'pendingNewsAction';
  private static readonly PENDING_SAVE_ARTICLE_URL_KEY = 'pendingSaveArticleUrl';
  private static readonly SAVE_ACTION = 'save';

  // Injection des dépendances Angular (services + router)
  private readonly route = inject(ActivatedRoute); // pour récupérer les paramètres de l’URL
  private readonly router = inject(Router); // pour naviguer entre pages
  private readonly newsService = inject(NewsService); // service pour récupérer les news
  private readonly favoritesService = inject(FavoritesService); // service favoris
  private readonly commentsService = inject(CommentsService); // service commentaires

  // Données du composant
  article: NewsArticle | null = null; // article affiché
  loading = true; // état de chargement
  error = ''; // message d’erreur

  comments: NewsComment[] = []; 
  commentText = ''; 
  commentError = ''; 
  loadingComments = false; 
  submittingComment = false; 

  saveError = ''; 
  isSaving = false; 
  isSaved = false; 

  loginReturnUrl = ''; // URL de retour après login

  // Méthode appelée au démarrage du composant
  ngOnInit(): void {

    this.loginReturnUrl = this.router.url;

    const articleId = this.route.snapshot.paramMap.get('id');

    const categoryParam = this.route.snapshot.queryParamMap.get('category') as
      | Exclude<NewsCategory, 'all'>
      | null;

    // Récupération d’un article passé via navigation (state)
    const stateArticle = (window.history.state?.article as NewsArticle | undefined) ?? null;

    if (!articleId) {
      this.error = 'Article not found.';
      this.loading = false;
      return;
    }

    const cachedArticle = this.getCachedArticle(articleId);

    // Si l’article est déjà dans le state → pas besoin d’appel API
    if (stateArticle && stateArticle.id === articleId) {
      this.article = stateArticle;
      this.cacheCurrentArticle();
      this.loading = false;
      this.loadSavedState(); // vérifier si favori
      this.loadComments(); // charger commentaires
      return;
    }

    // Le state Angular est perdu après un passage par la page login.
    if (cachedArticle && cachedArticle.id === articleId) {
      this.article = cachedArticle;
      this.loading = false;
      this.loadSavedState(); // vérifier si favori
      this.loadComments(); // charger commentaires
      return;
    }

    // Sinon → appel API pour récupérer l’article
    this.newsService.getArticleById(articleId, categoryParam ?? undefined).subscribe({
      next: (article) => {
        this.article = article;
        if (article) {
          this.cacheCurrentArticle();
        }
        this.error = article ? '' : 'Article not found.';
        this.loading = false;
        this.loadSavedState();
        this.loadComments();
      },
      error: () => {
        this.error = 'Unable to load article details right now.';
        this.loading = false;
      }
    });
  }

  // Ajouter ou retirer un article des favoris
  toggleSaveArticle(): void {

    if (!this.article) {
      return;
    }

    // Vérification URL valide
    if (!this.article.url || this.article.url === '#') {
      this.saveError = 'This article cannot be saved because the source URL is missing.';
      return;
    }

    const userId = this.getCurrentUserId();  //=> 203
    // récupérer l'utilisateur connecté

    if (!userId) { 
      this.markPendingSaveIntent();
      this.redirectToLogin(); // redirection si non connecté => 225
      return;
    }

    this.saveError = '';
    this.isSaving = true;

    // Si déjà sauvegardé → supprimer
    if (this.isSaved) {
      this.favoritesService.removeArticle(userId, this.article.url).subscribe({
        next: () => {
          this.isSaved = false;
          this.isSaving = false;
        },
        error: () => {
          this.saveError = 'Unable to remove the article right now.';
          this.isSaving = false;
        }
      });
      return;
    }

    // Sinon → sauvegarder  => favorites 28
    this.favoritesService.saveArticle(userId, this.article).subscribe({
      next: () => {   
        this.isSaved = true;
        this.isSaving = false;
      },
      error: (error) => {

        // Si erreur d’authentification → login
        if (this.isAuthError(error)) {
          this.isSaving = false;
          this.markPendingSaveIntent();
          this.redirectToLogin();
          return;
        }

        this.saveError = 'Unable to save the article right now.';
        this.isSaving = false;
      }
    });
  }

  // Poster un commentaire
  submitComment(): void {
    //article existe ?
    if (!this.article) {
      return;
    }
    //user id existe ?
    const userId = this.getCurrentUserId();

    if (!userId) {
      this.redirectToLogin();
      return;
    }
    //comment valide ?
    const cleanedComment = this.commentText.trim();// suppression espaces inutiles

    if (!cleanedComment) { 
      this.commentError = 'Write a comment before posting.';
      return;
    }

    this.commentError = '';
    this.submittingComment = true;

    // Appel service pour ajouter commentaire
    this.commentsService.addComment(userId, this.article, cleanedComment).subscribe({
      next: () => {
        this.commentText = ''; // reset champ
        this.submittingComment = false;
        this.loadComments(); // recharger commentaires
      },
      error: (error) => {

        if (this.isAuthError(error)) {
          this.submittingComment = false;
          this.redirectToLogin();
          return;
        }

        this.commentError = 'Unable to post the comment right now.';
        this.submittingComment = false;
      }
    });
  }

  // Récupérer l’ID utilisateur depuis localStorage
  private getCurrentUserId(): number | null { // s.n : null => 107
    //cmnt : => html 77
    const storedUser = localStorage.getItem('currentUser');

    if (!storedUser) {
      return null;
    }

    try {
      const parsed = JSON.parse(storedUser) as { id?: unknown };

      // Conversion en nombre
      const numericId = typeof parsed.id === 'number' ? parsed.id : Number(parsed.id); // support string ID that can be converted to number

      return Number.isFinite(numericId) ? numericId : null;// Si l’ID n’est pas un nombre valide → null

    } catch {
      return null;
    }
  }

  // Redirection vers login
  private redirectToLogin(): void { // app.routes.ts => 16
    this.cacheCurrentArticle();
    this.router.navigate(['/login'], { queryParams: { returnUrl: this.loginReturnUrl } });
  }  //La route /login pointe vers AuthCard:

  private cacheCurrentArticle(): void {
    if (!this.article) {
      return;
    }

    try {
      sessionStorage.setItem(
        NewsDetailsPageComponent.LAST_VIEWED_ARTICLE_KEY,
        JSON.stringify(this.article)
      );
    } catch {
      // Ignore cache write errors (private mode/storage quota).
    }
  }

  private getCachedArticle(expectedId: string): NewsArticle | null {
    try {
      const raw = sessionStorage.getItem(NewsDetailsPageComponent.LAST_VIEWED_ARTICLE_KEY);
      if (!raw) {
        return null;
      }

      const parsed = JSON.parse(raw) as Partial<NewsArticle> | null;
      if (!parsed || parsed.id !== expectedId) {
        return null;
      }

      return parsed as NewsArticle;
    } catch {
      return null;
    }
  }

  private markPendingSaveIntent(): void {
    if (!this.article || !this.article.url || this.article.url === '#') {
      return;
    }

    try {
      sessionStorage.setItem(
        NewsDetailsPageComponent.PENDING_SAVE_ACTION_KEY,
        NewsDetailsPageComponent.SAVE_ACTION
      );
      sessionStorage.setItem(
        NewsDetailsPageComponent.PENDING_SAVE_ARTICLE_URL_KEY,
        this.article.url
      );
    } catch {
      // Ignore cache write errors.
    }
  }

  private clearPendingSaveIntent(): void {
    try {
      sessionStorage.removeItem(NewsDetailsPageComponent.PENDING_SAVE_ACTION_KEY);
      sessionStorage.removeItem(NewsDetailsPageComponent.PENDING_SAVE_ARTICLE_URL_KEY);
    } catch {
      // Ignore cache removal errors.
    }
  }

  private consumePendingSaveIntent(): boolean {
    if (!this.article || !this.article.url || this.article.url === '#') {
      return false;
    }

    try {
      const action = sessionStorage.getItem(NewsDetailsPageComponent.PENDING_SAVE_ACTION_KEY);
      const pendingUrl = sessionStorage.getItem(NewsDetailsPageComponent.PENDING_SAVE_ARTICLE_URL_KEY);

      const shouldAutoSave =
        action === NewsDetailsPageComponent.SAVE_ACTION && pendingUrl === this.article.url;

      if (shouldAutoSave) {
        this.clearPendingSaveIntent();
      }

      return shouldAutoSave;
    } catch {
      return false;
    }
  }

  private autoSaveIfPending(userId: number): void {
    if (!this.article || !this.consumePendingSaveIntent()) {
      return;
    }

    this.saveError = '';
    this.isSaving = true;

    this.favoritesService.saveArticle(userId, this.article).subscribe({
      next: () => {
        this.isSaved = true;
        this.isSaving = false;
      },
      error: () => {
        this.saveError = 'Unable to save the article right now.';
        this.isSaving = false;
      }
    });
  }

  // Vérifie si erreur est liée à authentification
  private isAuthError(error: unknown): boolean {

    if (typeof error !== 'object' || error === null) {
      return false;
    }

    const status = 'status' in error ? Number((error as { status?: unknown }).status) : NaN;

    return status === 401 || status === 403;
  }

  // Vérifier si article est sauvegardé
  private loadSavedState(): void {

    const userId = this.getCurrentUserId();

    if (!this.article || !userId || !this.article.url || this.article.url === '#') {
      this.isSaved = false;
      return;
    }

    this.favoritesService.isArticleSaved(userId, this.article.url).subscribe((saved) => {
      this.isSaved = saved;

      if (saved) {
        this.clearPendingSaveIntent();
        return;
      }

      this.autoSaveIfPending(userId);
    });
  }

  // Charger les commentaires
  private loadComments(): void {

    if (!this.article || !this.article.url || this.article.url === '#') {
      this.comments = [];
      return;
    }

    this.loadingComments = true;

    this.commentsService.getComments(this.article.url).subscribe({
      next: (comments) => {
        this.comments = comments;
        this.loadingComments = false;
      },
      error: () => {
        this.comments = [];
        this.loadingComments = false;
      }
    });
  }

  // Vérifie si utilisateur connecté
  isLoggedIn(): boolean {
    return this.getCurrentUserId() !== null; //=> 203
  }
}