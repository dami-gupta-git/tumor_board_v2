import { Injectable } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Observable, throwError } from 'rxjs';
import { catchError } from 'rxjs/operators';

export interface VariantInput {
  gene: string;
  variant: string;
  tumor_type?: string;
}

export interface RecommendedTherapy {
  drug_name: string;
  evidence_level?: string;
  approval_status?: string;
  clinical_context?: string;
}

export interface AssessmentResponse {
  variant: {
    gene: string;
    variant: string;
    tumor_type?: string;
  };
  assessment: {
    tier: string;
    confidence: number;
    rationale: string;
    summary: string;
    evidence_strength?: string;
  };
  identifiers: {
    cosmic_id?: string;
    ncbi_gene_id?: string;
    dbsnp_id?: string;
    clinvar_id?: string;
  };
  hgvs: {
    genomic?: string;
    protein?: string;
    transcript?: string;
  };
  clinvar: {
    clinical_significance?: string;
    accession?: string;
  };
  annotations: {
    snpeff_effect?: string;
    polyphen2_prediction?: string;
    cadd_score?: number;
    gnomad_exome_af?: number;
  };
  transcript: {
    id?: string;
    consequence?: string;
  };
  recommended_therapies: RecommendedTherapy[];
}

export interface HealthResponse {
  status: string;
  service: string;
}

@Injectable({
  providedIn: 'root'
})
export class TumorboardApiService {
  private apiUrl = '/api';

  constructor(private http: HttpClient) {}

  /**
   * Check API health status
   */
  healthCheck(): Observable<HealthResponse> {
    return this.http.get<HealthResponse>(`${this.apiUrl}/health`)
      .pipe(catchError(this.handleError));
  }

  /**
   * Assess a variant for clinical actionability
   */
  assessVariant(variantInput: VariantInput): Observable<AssessmentResponse> {
    return this.http.post<AssessmentResponse>(`${this.apiUrl}/assess`, variantInput)
      .pipe(catchError(this.handleError));
  }

  /**
   * Get raw evidence for a variant
   */
  getEvidence(gene: string, variant: string): Observable<any> {
    return this.http.get<any>(`${this.apiUrl}/evidence/${gene}/${variant}`)
      .pipe(catchError(this.handleError));
  }

  /**
   * Handle HTTP errors
   */
  private handleError(error: HttpErrorResponse) {
    let errorMessage = 'An unknown error occurred';

    if (error.error instanceof ErrorEvent) {
      // Client-side error
      errorMessage = `Error: ${error.error.message}`;
    } else {
      // Server-side error
      if (error.error && error.error.error) {
        errorMessage = error.error.error;
      } else {
        errorMessage = `Server returned code ${error.status}: ${error.message}`;
      }
    }

    return throwError(() => new Error(errorMessage));
  }
}
