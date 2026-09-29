package synkora

import "fmt"

// SynkoraError is the base error type for all SDK errors.
type SynkoraError struct {
	Message    string
	StatusCode int // 0 when not applicable
}

func (e *SynkoraError) Error() string {
	if e.StatusCode != 0 {
		return fmt.Sprintf("synkora: %s (HTTP %d)", e.Message, e.StatusCode)
	}
	return "synkora: " + e.Message
}

// AuthError is returned when the API key is missing, invalid, or lacks permission.
type AuthError struct{ SynkoraError }

// AgentNotFoundError is returned when the requested agent does not exist.
type AgentNotFoundError struct{ SynkoraError }

// RateLimitError is returned when the API rate limit has been exceeded.
type RateLimitError struct{ SynkoraError }

// StreamError is returned when an error event is received in the SSE stream.
type StreamError struct {
	SynkoraError
	ErrorType   string
	ViolationID string
}

// APIError is returned for unexpected server errors (5xx) or malformed responses.
type APIError struct{ SynkoraError }

func errAuth(msg string, code int) error {
	return &AuthError{SynkoraError{Message: msg, StatusCode: code}}
}

func errNotFound(msg string, code int) error {
	return &AgentNotFoundError{SynkoraError{Message: msg, StatusCode: code}}
}

func errRateLimit(msg string, code int) error {
	return &RateLimitError{SynkoraError{Message: msg, StatusCode: code}}
}

func errAPI(msg string, code int) error {
	return &APIError{SynkoraError{Message: msg, StatusCode: code}}
}

func errStream(msg, errType, violationID string) error {
	return &StreamError{
		SynkoraError: SynkoraError{Message: msg},
		ErrorType:    errType,
		ViolationID:  violationID,
	}
}
