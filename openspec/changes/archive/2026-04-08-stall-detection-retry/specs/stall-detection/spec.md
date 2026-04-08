## ADDED Requirements

### Requirement: Idle timeout configuration
The system SHALL support an `idle_timeout` configuration parameter in `TimeoutsConfig` that specifies the maximum allowed duration (in seconds) with no stdout output from a provider before the invocation is considered stalled. The parameter SHALL default to `None` (disabled). When set, the minimum value SHALL be 30 seconds.

#### Scenario: idle_timeout is configured globally
- **WHEN** `timeouts.idle_timeout` is set to 180 in the YAML config
- **THEN** all phases SHALL use 180 seconds as the idle timeout threshold

#### Scenario: idle_timeout is not configured
- **WHEN** `timeouts.idle_timeout` is not set (None)
- **THEN** idle timeout detection SHALL be completely disabled and behavior SHALL be identical to before this change

#### Scenario: idle_timeout validation rejects values below minimum
- **WHEN** `timeouts.idle_timeout` is set to a value less than 30
- **THEN** configuration validation SHALL reject the value with an appropriate error message

### Requirement: Stall detection for subprocess providers
The system SHALL monitor the stdout output stream of subprocess-based providers (Claude, Gemini, Kimi, Codex, Copilot, Amp, CursorAgent, OpenCode) and detect when no new output has been received for longer than the configured `idle_timeout` duration.

#### Scenario: Provider produces output within idle_timeout
- **WHEN** a subprocess provider produces at least one line of stdout output within every `idle_timeout` interval
- **THEN** the invocation SHALL continue normally until completion or total timeout

#### Scenario: Provider stops producing output beyond idle_timeout
- **WHEN** a subprocess provider produces no stdout output for a duration exceeding `idle_timeout`
- **THEN** the system SHALL terminate the provider process and raise `ProviderTimeoutError` with a message indicating idle timeout

#### Scenario: Idle timer resets on each output line
- **WHEN** a provider produces a line of stdout output
- **THEN** the idle timer SHALL reset to zero, regardless of how long the gap was between previous outputs

### Requirement: Stall detection for SDK providers
The system SHALL monitor the message stream of SDK-based providers (ClaudeSDKProvider) and detect when no new messages have been received for longer than the configured `idle_timeout` duration.

#### Scenario: SDK provider stops producing messages beyond idle_timeout
- **WHEN** a SDK provider produces no new messages for a duration exceeding `idle_timeout`
- **THEN** the system SHALL cancel the SDK invocation and raise `ProviderTimeoutError` with a message indicating idle timeout

### Requirement: Stall-triggered retry via existing retry mechanism
When idle timeout is detected, the system SHALL raise `ProviderTimeoutError` which is handled by the existing `invoke_with_timeout_retry` mechanism. This means stall detection automatically benefits from the configured `timeouts.retries` setting.

#### Scenario: Stall detected with retries configured
- **WHEN** idle timeout is detected AND `timeouts.retries` is set to a value > 0
- **THEN** the system SHALL automatically retry the provider invocation (same as total timeout retry behavior)

#### Scenario: Stall detected with no retries configured
- **WHEN** idle timeout is detected AND `timeouts.retries` is None
- **THEN** the system SHALL raise `ProviderTimeoutError` immediately without retry

#### Scenario: Stall detected with fallback provider
- **WHEN** idle timeout is detected AND retries are exhausted AND a fallback provider is configured
- **THEN** the system SHALL invoke the fallback provider (same as total timeout fallback behavior)

### Requirement: Thread-safe last-output timestamp tracking
The system SHALL use a thread-safe mechanism to track the timestamp of the last stdout output from the provider process. The timestamp SHALL be updated by the stream reader thread and read by the poll loop thread.

#### Scenario: Concurrent read and write of last_output_time
- **WHEN** the stream reader thread updates last_output_time while the poll loop thread reads it
- **THEN** no data corruption or race condition SHALL occur

### Requirement: Idle timeout and total timeout independence
The idle timeout and total timeout SHALL operate independently. The idle timeout checks for gaps in output, while the total timeout enforces maximum execution time. Both can trigger termination.

#### Scenario: Total timeout triggers before idle timeout
- **WHEN** a provider continuously produces output but exceeds the total phase timeout
- **THEN** the total timeout SHALL terminate the process (idle timeout does not prevent total timeout)

#### Scenario: Idle timeout triggers before total timeout
- **WHEN** a provider stops producing output and `idle_timeout` is reached before the total phase timeout
- **THEN** the idle timeout SHALL terminate the process without waiting for the total timeout
