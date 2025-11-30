import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClientModule } from '@angular/common/http';

import { TumorboardApiService, VariantInput, AssessmentResponse } from './services/tumorboard-api.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, FormsModule, HttpClientModule],
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.scss']
})
export class AppComponent {
  title = 'TumorBoard';

  // Form model
  variantInput: VariantInput = {
    gene: '',
    variant: '',
    tumor_type: ''
  };

  // State
  isLoading = false;
  error: string | null = null;
  assessment: AssessmentResponse | null = null;
  apiHealthy = false;

  constructor(private apiService: TumorboardApiService) {
    this.checkApiHealth();
  }

  /**
   * Check if the API is healthy
   */
  checkApiHealth(): void {
    this.apiService.healthCheck().subscribe({
      next: (response) => {
        this.apiHealthy = response.status === 'healthy';
      },
      error: (error) => {
        this.apiHealthy = false;
        console.error('API health check failed:', error);
      }
    });
  }

  /**
   * Submit variant for assessment
   */
  onSubmit(): void {
    // Reset state
    this.error = null;
    this.assessment = null;

    // Validate input
    if (!this.variantInput.gene || !this.variantInput.variant) {
      this.error = 'Both gene and variant are required';
      return;
    }

    // Start loading
    this.isLoading = true;

    // Call API
    this.apiService.assessVariant(this.variantInput).subscribe({
      next: (response) => {
        this.assessment = response;
        this.isLoading = false;
      },
      error: (error) => {
        this.error = error.message;
        this.isLoading = false;
      }
    });
  }

  /**
   * Reset form and results
   */
  reset(): void {
    this.variantInput = {
      gene: '',
      variant: '',
      tumor_type: ''
    };
    this.assessment = null;
    this.error = null;
  }

  /**
   * Get CSS class for tier badge
   */
  getTierClass(tier: string): string {
    return `tier-badge tier-${tier.toLowerCase().replace(' ', '-')}`;
  }

  /**
   * Format allele frequency for display
   */
  formatAlleleFrequency(af: number | undefined): string {
    if (af === undefined || af === null) return 'N/A';
    return af.toExponential(2);
  }

  /**
   * Format CADD score for display
   */
  formatCaddScore(score: number | undefined): string {
    if (score === undefined || score === null) return 'N/A';
    return score.toFixed(2);
  }

  /**
   * Get interpretation for PolyPhen2 prediction
   */
  getPolyPhen2Interpretation(pred: string | undefined): string {
    if (!pred) return 'N/A';
    switch (pred) {
      case 'D': return 'Damaging';
      case 'P': return 'Possibly Damaging';
      case 'B': return 'Benign';
      default: return pred;
    }
  }
}
