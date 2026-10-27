import type { PassportCardData } from '../components/PassportCard'

// Public illustration only. Never used as a fallback for private API data.
export const demonstrationPassport: PassportCardData = {
  demonstration: true, firstName: 'Alex', lastName: 'Example', issuer: null, reference: null, issuedOn: null, status: 'DEMONSTRATION',
  skills: [
    { id: 'sample-focus', name: 'Responsible AI', stampType: 'FOCUSED', description: 'Recognizing limitations and evaluating AI-generated information.', experience: 'Fictional AI literacy workshop', earnedOn: null },
    { id: 'sample-applied', name: 'AI prototyping', stampType: 'APPLIED', description: 'Applying AI tools to a practical prototype.', experience: 'Fictional two-day hackathon', earnedOn: null },
    { id: 'sample-advanced', name: 'Machine learning', stampType: 'ADVANCED', description: 'Developing and assessing machine-learning methods.', experience: 'Fictional semester-long course', earnedOn: null },
  ],
}
