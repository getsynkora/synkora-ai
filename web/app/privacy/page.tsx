import Link from 'next/link'
import PublicPageFrame from '@/components/public/PublicPageFrame'

export const metadata = {
  title: 'Privacy Policy – Synkora',
  description: 'Synkora Privacy Policy. Explains how we collect, use, and protect data on the Synkora LLM platform. Self-hosted deployments give you full data control.',
}

export default function PrivacyPolicyPage() {
  return (
    <PublicPageFrame mainClassName="pt-28 pb-12 px-4">
      <div className="max-w-4xl mx-auto bg-white rounded-2xl shadow-xl border border-gray-100 p-8 md:p-12">
        {/* Header */}
        <div className="mb-8">
          <Link 
            href="/signin" 
            className="inline-flex items-center text-primary-500 hover:text-primary-600 mb-6"
          >
            <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
            </svg>
            Back to Sign In
          </Link>
          <h1 className="text-4xl font-bold text-gray-900 mb-4">Privacy Policy</h1>
          <p className="text-gray-600">Last updated: December 24, 2025</p>
        </div>

        {/* Content */}
        <div className="prose prose-red max-w-none">
          <section className="mb-8">
            <h2 className="text-2xl font-semibold text-gray-900 mb-4">1. Introduction</h2>
            <p className="text-gray-700 mb-4">
              Welcome to Synkora. We respect your privacy and are committed to protecting your personal data. 
              This privacy policy will inform you about how we handle your personal data when you use our 
              platform and tell you about your privacy rights.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold text-gray-900 mb-4">2. Information We Collect</h2>
            <p className="text-gray-700 mb-4">We collect and process the following types of information:</p>
            
            <h3 className="text-xl font-semibold text-gray-900 mb-3 mt-4">2.1 Information You Provide</h3>
            <ul className="list-disc list-inside text-gray-700 mb-4 ml-4">
              <li>Account information (name, email address, password)</li>
              <li>Profile information</li>
              <li>Payment and billing information</li>
              <li>Content you create or upload (agents, knowledge bases, etc.)</li>
              <li>Communications with our support team</li>
            </ul>

            <h3 className="text-xl font-semibold text-gray-900 mb-3 mt-4">2.2 Automatically Collected Information</h3>
            <ul className="list-disc list-inside text-gray-700 mb-4 ml-4">
              <li>Usage data and analytics</li>
              <li>Device information (IP address, browser type, operating system)</li>
              <li>Cookies and similar tracking technologies</li>
              <li>Log files and error reports</li>
            </ul>
          </section>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold text-gray-900 mb-4">3. How We Use Your Information</h2>
            <p className="text-gray-700 mb-4">We use your information for the following purposes:</p>
            <ul className="list-disc list-inside text-gray-700 mb-4 ml-4">
              <li>To provide and maintain our services</li>
              <li>To process your transactions and manage your account</li>
              <li>To communicate with you about your account and our services</li>
              <li>To improve and optimize our platform</li>
              <li>To detect and prevent fraud and abuse</li>
              <li>To comply with legal obligations</li>
              <li>To send you marketing communications (with your consent)</li>
            </ul>
          </section>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold text-gray-900 mb-4">4. Legal Basis for Processing</h2>
            <p className="text-gray-700 mb-4">We process your personal data based on:</p>
            <ul className="list-disc list-inside text-gray-700 mb-4 ml-4">
              <li><strong>Contract performance:</strong> To provide our services to you</li>
              <li><strong>Legitimate interests:</strong> To improve our services and prevent fraud</li>
              <li><strong>Legal obligations:</strong> To comply with applicable laws</li>
              <li><strong>Consent:</strong> For marketing communications and certain data processing activities</li>
            </ul>
          </section>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold text-gray-900 mb-4">5. Data Sharing and Disclosure</h2>
            <p className="text-gray-700 mb-4">We may share your information with:</p>
            <ul className="list-disc list-inside text-gray-700 mb-4 ml-4">
              <li><strong>Service providers:</strong> Third-party vendors who help us operate our platform</li>
              <li><strong>Payment processors:</strong> To process your payments securely</li>
              <li><strong>Analytics providers:</strong> To understand how our services are used</li>
              <li><strong>Legal authorities:</strong> When required by law or to protect our rights</li>
              <li><strong>Business transfers:</strong> In connection with a merger, acquisition, or sale of assets</li>
            </ul>
            <p className="text-gray-700 mb-4">
              We do not sell your personal data to third parties.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold text-gray-900 mb-4">6. Data Security</h2>
            <p className="text-gray-700 mb-4">
              We implement appropriate technical and organizational measures to protect your personal data, including:
            </p>
            <ul className="list-disc list-inside text-gray-700 mb-4 ml-4">
              <li>Encryption of data in transit and at rest</li>
              <li>Regular security assessments and audits</li>
              <li>Access controls and authentication</li>
              <li>Secure infrastructure and hosting</li>
              <li>Employee training on data protection</li>
            </ul>
          </section>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold text-gray-900 mb-4">7. Data Retention</h2>
            <p className="text-gray-700 mb-4">
              We retain your personal data only for as long as necessary to fulfill the purposes outlined in 
              this privacy policy, unless a longer retention period is required by law. When your data is no 
              longer needed, we will securely delete or anonymize it.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold text-gray-900 mb-4">8. Your Privacy Rights</h2>
            <p className="text-gray-700 mb-4">Depending on your location, you may have the following rights:</p>
            <ul className="list-disc list-inside text-gray-700 mb-4 ml-4">
              <li><strong>Access:</strong> Request a copy of your personal data</li>
              <li><strong>Rectification:</strong> Correct inaccurate or incomplete data</li>
              <li><strong>Erasure:</strong> Request deletion of your personal data</li>
              <li><strong>Restriction:</strong> Limit how we process your data</li>
              <li><strong>Portability:</strong> Receive your data in a portable format</li>
              <li><strong>Objection:</strong> Object to certain processing activities</li>
              <li><strong>Withdraw consent:</strong> Withdraw your consent at any time</li>
            </ul>
            <p className="text-gray-700 mb-4">
              To exercise these rights, please contact us at{' '}
              <a href="mailto:privacy@synkora.ai" className="text-primary-500 hover:text-primary-600">
                privacy@synkora.ai
              </a>
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold text-gray-900 mb-4">9. Cookies and Tracking</h2>
            <p className="text-gray-700 mb-4">
              We use cookies and similar tracking technologies to improve your experience. You can control 
              cookies through your browser settings. However, disabling cookies may affect the functionality 
              of our services.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold text-gray-900 mb-4">10. International Data Transfers</h2>
            <p className="text-gray-700 mb-4">
              Your information may be transferred to and processed in countries other than your own. We ensure 
              appropriate safeguards are in place to protect your data in accordance with this privacy policy 
              and applicable laws.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold text-gray-900 mb-4">11. Children's Privacy</h2>
            <p className="text-gray-700 mb-4">
              Our services are not intended for children under 13 years of age. We do not knowingly collect 
              personal data from children. If you believe we have collected data from a child, please contact us.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold text-gray-900 mb-4">12. Third-Party Links</h2>
            <p className="text-gray-700 mb-4">
              Our platform may contain links to third-party websites or services. We are not responsible for 
              the privacy practices of these third parties. We encourage you to review their privacy policies.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold text-gray-900 mb-4">13. Changes to This Policy</h2>
            <p className="text-gray-700 mb-4">
              We may update this privacy policy from time to time. We will notify you of any material changes 
              by posting the new policy on this page and updating the "Last updated" date. Your continued use 
              of our services after such changes constitutes acceptance of the updated policy.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold text-gray-900 mb-4">14. Contact Us</h2>
            <p className="text-gray-700 mb-4">
              If you have any questions about this Privacy Policy or our data practices, please contact us:
            </p>
            <p className="text-gray-700 mb-2">
              Email: <a href="mailto:privacy@synkora.ai" className="text-primary-500 hover:text-primary-600">privacy@synkora.ai</a>
            </p>
            <p className="text-gray-700">
              Support: <a href="mailto:support@synkora.ai" className="text-primary-500 hover:text-primary-600">support@synkora.ai</a>
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold text-gray-900 mb-4">15. California Privacy Rights</h2>
            <p className="text-gray-700 mb-4">
              If you are a California resident, you have additional rights under the California Consumer Privacy 
              Act (CCPA), including the right to know what personal information we collect, use, and disclose, 
              and the right to request deletion of your personal information.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold text-gray-900 mb-4">16. GDPR Compliance</h2>
            <p className="text-gray-700 mb-4">
              If you are located in the European Economic Area (EEA), we comply with the General Data Protection 
              Regulation (GDPR). You have the rights outlined in Section 8 of this policy, and you may lodge a 
              complaint with your local data protection authority.
            </p>
          </section>
        </div>
      </div>
    </PublicPageFrame>
  )
}
