/** Base class for all Synkora SDK errors. */
export class SynkoraError extends Error {
  readonly statusCode: number | undefined

  constructor(message: string, statusCode?: number) {
    super(message)
    this.name = 'SynkoraError'
    this.statusCode = statusCode
    // Maintain proper prototype chain in transpiled ES5
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

/** API key is missing, invalid, or lacks the required permission. */
export class AuthError extends SynkoraError {
  constructor(message: string, statusCode?: number) {
    super(message, statusCode)
    this.name = 'AuthError'
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

/** The requested agent does not exist or is not accessible. */
export class AgentNotFoundError extends SynkoraError {
  constructor(message: string, statusCode?: number) {
    super(message, statusCode)
    this.name = 'AgentNotFoundError'
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

/** API rate limit was exceeded. */
export class RateLimitError extends SynkoraError {
  constructor(message: string, statusCode?: number) {
    super(message, statusCode)
    this.name = 'RateLimitError'
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

/** An error event was received in the SSE stream. */
export class StreamError extends SynkoraError {
  readonly errorType: string | undefined
  readonly violationId: string | undefined

  constructor(message: string, errorType?: string, violationId?: string) {
    super(message)
    this.name = 'StreamError'
    this.errorType = errorType
    this.violationId = violationId
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

/** Unexpected server-side error (5xx) or malformed response. */
export class APIError extends SynkoraError {
  constructor(message: string, statusCode?: number) {
    super(message, statusCode)
    this.name = 'APIError'
    Object.setPrototypeOf(this, new.target.prototype)
  }
}
