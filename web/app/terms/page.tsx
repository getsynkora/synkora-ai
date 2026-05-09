import Link from 'next/link'

export const metadata = {
  title: 'Terms of Service – Synkora',
  description: 'Read the Synkora Terms of Service. Governs your use of the open-source LLM application platform, whether self-hosted or on Synkora Cloud.',
}

export default function TermsOfServicePage() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-red-50 via-white to-pink-50 py-12 px-4">
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
          <h1 className="text-4xl font-bold text-gray-900 mb-4">Terms of Service</h1>
          <p className="text-gray-600">Last updated: February 25, 2026</p>
        </div>

        {/* Content */}
        <div className="prose prose-red max-w-none">
          <section className="mb-8">
            <h2 className="text-2xl font-semibold text-gray-900 mb-4">1. Acceptance of Terms</h2>
            <p className="text-gray-700 mb-4">
              By accessing or using Synkora's services, you agree to be bound by these Terms of Service. 
              If you do not agree to these terms, please do not use our services.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold text-gray-900 mb-4">2. Description of Service</h2>
            <p className="text-gray-700 mb-4">
              Synkora provides an AI-powered agent platform that enables users to create, deploy, and manage 
              intelligent agents. Our services include but are not limited to:
            </p>
            <ul className="list-disc list-inside text-gray-700 mb-4 ml-4">
              <li>Agent creation and management</li>
              <li>Integration with third-party services</li>
              <li>API access for developers</li>
              <li>Knowledge base management</li>
              <li>Chat and messaging capabilities</li>
            </ul>
          </section>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold text-gray-900 mb-4">3. User Accounts</h2>
            <p className="text-gray-700 mb-4">
              To use our services, you must create an account. You are responsible for:
            </p>
            <ul className="list-disc list-inside text-gray-700 mb-4 ml-4">
              <li>Maintaining the confidentiality of your account credentials</li>
              <li>All activities that occur under your account</li>
              <li>Notifying us immediately of any unauthorized access</li>
              <li>Providing accurate and complete information</li>
            </ul>
          </section>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold text-gray-900 mb-4">4. Acceptable Use</h2>
            <p className="text-gray-700 mb-4">You agree not to:</p>
            <ul className="list-disc list-inside text-gray-700 mb-4 ml-4">
              <li>Use the service for any illegal or unauthorized purpose</li>
              <li>Violate any laws in your jurisdiction</li>
              <li>Infringe upon the rights of others</li>
              <li>Transmit any malicious code or viruses</li>
              <li>Attempt to gain unauthorized access to our systems</li>
              <li>Use the service to spam or harass others</li>
              <li>Reverse engineer or attempt to extract source code</li>
            </ul>
          </section>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold text-gray-900 mb-4">5. Intellectual Property</h2>
            <p className="text-gray-700 mb-4">
              All content, features, and functionality of Synkora are owned by us and are protected by 
              international copyright, trademark, and other intellectual property laws.
            </p>
            <p className="text-gray-700 mb-4">
              You retain ownership of any content you create or upload to our platform, but grant us 
              a license to use it to provide our services.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold text-gray-900 mb-4">6. Payment and Billing</h2>
            <p className="text-gray-700 mb-4">
              Certain features of our service may require payment. Our payment processing is handled by Paddle.com
              as the Merchant of Record. By subscribing to a paid plan:
            </p>
            <ul className="list-disc list-inside text-gray-700 mb-4 ml-4">
              <li>You agree to pay all fees associated with your subscription</li>
              <li>We may change our pricing with 30 days notice</li>
              <li>You authorize Paddle to charge your payment method automatically</li>
              <li>Paddle handles all payment processing, tax calculation, and compliance</li>
            </ul>
          </section>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold text-gray-900 mb-4">7. Refund Policy</h2>
            <p className="text-gray-700 mb-4">
              We offer a <strong>30-day money-back guarantee</strong> for new subscriptions. Our refund policy
              is as follows:
            </p>
            <h3 className="text-lg font-semibold text-gray-800 mt-4 mb-2">Eligibility for Refunds</h3>
            <ul className="list-disc list-inside text-gray-700 mb-4 ml-4">
              <li>Refund requests must be submitted within <strong>30 days</strong> of the initial purchase</li>
              <li>Refunds are provided at the sole discretion of Paddle (our payment processor) on a case-by-case basis</li>
              <li>There are <strong>no refunds</strong> on unused subscription periods after the 30-day guarantee window</li>
              <li>Refund requests for sales tax must be made within 60 days of the transaction</li>
            </ul>
            <h3 className="text-lg font-semibold text-gray-800 mt-4 mb-2">Refund Process</h3>
            <ul className="list-disc list-inside text-gray-700 mb-4 ml-4">
              <li>All refund requests should be submitted to our support team at support@synkora.ai</li>
              <li>Refunds are processed through Paddle, our Merchant of Record</li>
              <li>Approved refunds will be credited to the original payment method within 5-10 business days</li>
              <li>You will receive email confirmation once the refund is processed</li>
            </ul>
            <h3 className="text-lg font-semibold text-gray-800 mt-4 mb-2">Non-Refundable Items</h3>
            <ul className="list-disc list-inside text-gray-700 mb-4 ml-4">
              <li>Credit top-ups and consumable purchases</li>
              <li>Requests made after the 30-day guarantee period</li>
              <li>Accounts terminated for Terms of Service violations</li>
              <li>Cases where evidence of fraud, refund abuse, or manipulative behavior is found</li>
            </ul>
            <h3 className="text-lg font-semibold text-gray-800 mt-4 mb-2">Subscription Cancellation</h3>
            <p className="text-gray-700 mb-4">
              You may cancel your subscription at any time. Upon cancellation:
            </p>
            <ul className="list-disc list-inside text-gray-700 mb-4 ml-4">
              <li>You will retain access until the end of your current billing period</li>
              <li>No partial refunds are provided for unused time in the current billing cycle</li>
              <li>Recurring charges will stop at the end of the billing period</li>
            </ul>
          </section>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold text-gray-900 mb-4">8. Data and Privacy</h2>
            <p className="text-gray-700 mb-4">
              Your privacy is important to us. Please review our{' '}
              <Link href="/privacy" className="text-primary-500 hover:text-primary-600 font-medium">
                Privacy Policy
              </Link>
              {' '}to understand how we collect, use, and protect your data.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold text-gray-900 mb-4">9. Termination</h2>
            <p className="text-gray-700 mb-4">
              We reserve the right to suspend or terminate your account at any time for violations of
              these terms or for any other reason at our sole discretion. You may also terminate your
              account at any time by contacting us.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold text-gray-900 mb-4">10. Disclaimer of Warranties</h2>
            <p className="text-gray-700 mb-4">
              Our services are provided "as is" without warranties of any kind, either express or implied.
              We do not guarantee that our services will be uninterrupted, secure, or error-free.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold text-gray-900 mb-4">11. Limitation of Liability</h2>
            <p className="text-gray-700 mb-4">
              To the maximum extent permitted by law, Synkora shall not be liable for any indirect,
              incidental, special, consequential, or punitive damages resulting from your use of our services.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold text-gray-900 mb-4">12. Changes to Terms</h2>
            <p className="text-gray-700 mb-4">
              We reserve the right to modify these terms at any time. We will notify users of any
              material changes. Your continued use of our services after such modifications constitutes
              acceptance of the updated terms.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-2xl font-semibold text-gray-900 mb-4">13. Contact Us</h2>
            <p className="text-gray-700 mb-4">
              If you have any questions about these Terms of Service, please contact us at:
            </p>
            <p className="text-gray-700">
              Email: <a href="mailto:support@synkora.ai" className="text-primary-500 hover:text-primary-600">support@synkora.ai</a>
            </p>
          </section>
        </div>
      </div>
    </div>
  )
}
