package logging

import (
	"encoding/json"
	"log"
	"os"
)

// Logger is a structured JSON logger.
type Logger struct {
	Service string
}

// NewLogger creates a new Logger.
func NewLogger(service string) *Logger {
	return &Logger{Service: service}
}

// Info logs an info message.
func (l *Logger) Info(msg string, fields map[string]interface{}) {
	entry := map[string]interface{}{
		"level":   "INFO",
		"service": l.Service,
		"message": msg,
	}
	for k, v := range fields {
		entry[k] = v
	}
	b, _ := json.Marshal(entry)
	log.Println(string(b))
}

// Error logs an error message.
func (l *Logger) Error(msg string, err error, fields map[string]interface{}) {
	entry := map[string]interface{}{
		"level":   "ERROR",
		"service": l.Service,
		"message": msg,
		"error":   err.Error(),
	}
	for k, v := range fields {
		entry[k] = v
	}
	b, _ := json.Marshal(entry)
	log.Println(string(b))
}
