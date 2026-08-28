package errors

import "fmt"

// SentraAuraError is the base error type for SentraAura Go services.
type SentraAuraError struct {
	Code    string
	Message string
	TraceID string
	Details map[string]interface{}
}

func (e *SentraAuraError) Error() string {
	return fmt.Sprintf("[%s] %s (trace: %s)", e.Code, e.Message, e.TraceID)
}

// NewError creates a new SentraAuraError.
func NewError(code, message, traceID string) *SentraAuraError {
	return &SentraAuraError{
		Code:    code,
		Message: message,
		TraceID: traceID,
		Details: make(map[string]interface{}),
	}
}

// TransientError indicates a retryable error.
type TransientError struct {
	SentraAuraError
}

// NewTransientError creates a new TransientError.
func NewTransientError(message, traceID string) *TransientError {
	return &TransientError{
		SentraAuraError: *NewError("TRANSIENT_ERROR", message, traceID),
	}
}
