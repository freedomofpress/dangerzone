//! Container execution and data passing.
//!
//! This module provides functionality to run containers and pass data to them.

use std::io::{self, Write};
use std::process::{Child, Command, Stdio};

/// Errors that can occur during container operations.
#[derive(Debug, thiserror::Error)]
pub enum ContainerError {
    #[error("IO error: {0}")]
    Io(#[from] io::Error),

    #[error("Container execution failed: {0}")]
    ExecutionFailed(String),

    #[error("Invalid container name: {0}")]
    InvalidName(String),
}

/// Runs containers and manages their execution.
pub struct ContainerRunner {
    container_name: String,
    runtime: ContainerRuntime,
}

/// Supported container runtimes.
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum ContainerRuntime {
    Podman,
    Docker,
}

impl ContainerRuntime {
    /// Returns the command name for this runtime.
    pub fn command(&self) -> &str {
        match self {
            ContainerRuntime::Podman => "podman",
            ContainerRuntime::Docker => "docker",
        }
    }

    /// Detects which container runtime is available on the system.
    pub fn detect() -> Result<Self, ContainerError> {
        // Try podman first
        if Command::new("podman")
            .arg("--version")
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status()
            .is_ok()
        {
            return Ok(ContainerRuntime::Podman);
        }

        // Try docker
        if Command::new("docker")
            .arg("--version")
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status()
            .is_ok()
        {
            return Ok(ContainerRuntime::Docker);
        }

        Err(ContainerError::ExecutionFailed(
            "No container runtime (podman or docker) found".to_string(),
        ))
    }
}

impl ContainerRunner {
    /// Creates a new ContainerRunner with the specified container name.
    pub fn new(container_name: String) -> Self {
        ContainerRunner {
            container_name,
            runtime: ContainerRuntime::Podman, // default to podman
        }
    }

    /// Creates a new ContainerRunner with a specific runtime.
    pub fn with_runtime(container_name: String, runtime: ContainerRuntime) -> Self {
        ContainerRunner {
            container_name,
            runtime,
        }
    }

    /// Creates a ContainerRunner with auto-detected runtime.
    pub fn with_auto_runtime(container_name: String) -> Result<Self, ContainerError> {
        let runtime = ContainerRuntime::detect()?;
        Ok(ContainerRunner {
            container_name,
            runtime,
        })
    }

    /// Executes a container with the given command and arguments.
    ///
    /// Returns a Child process that can be used to interact with the container.
    pub fn run(
        &self,
        image: &str,
        command: &[&str],
        extra_args: &[&str],
    ) -> Result<Child, ContainerError> {
        if self.container_name.is_empty() {
            return Err(ContainerError::InvalidName(
                "Container name cannot be empty".to_string(),
            ));
        }

        let mut cmd = Command::new(self.runtime.command());
        cmd.arg("run")
            .arg("-i") // Interactive mode (keep stdin open)
            .arg("--rm") // Remove container after exit
            .arg("--name")
            .arg(&self.container_name);

        // Add extra arguments
        for arg in extra_args {
            cmd.arg(arg);
        }

        cmd.arg(image);

        // Add the command to run in the container
        for arg in command {
            cmd.arg(arg);
        }

        cmd.stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());

        cmd.spawn().map_err(ContainerError::from)
    }

    /// Executes a container and passes input data to it via stdin.
    ///
    /// Returns the child process with stdin already written and closed.
    pub fn run_with_input(
        &self,
        image: &str,
        command: &[&str],
        extra_args: &[&str],
        input_data: &[u8],
    ) -> Result<Child, ContainerError> {
        let mut child = self.run(image, command, extra_args)?;

        // Write input data to the container's stdin
        if let Some(mut stdin) = child.stdin.take() {
            stdin.write_all(input_data).map_err(ContainerError::from)?;
            // stdin is automatically closed when dropped
        }

        Ok(child)
    }

    /// Gets the container name.
    pub fn container_name(&self) -> &str {
        &self.container_name
    }

    /// Gets the runtime being used.
    pub fn runtime(&self) -> ContainerRuntime {
        self.runtime
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_new_container_runner() {
        let runner = ContainerRunner::new("test-container".to_string());
        assert_eq!(runner.container_name(), "test-container");
        assert_eq!(runner.runtime(), ContainerRuntime::Podman);
    }

    #[test]
    fn test_with_runtime() {
        let runner =
            ContainerRunner::with_runtime("test-container".to_string(), ContainerRuntime::Docker);
        assert_eq!(runner.runtime(), ContainerRuntime::Docker);
    }

    #[test]
    fn test_runtime_command() {
        assert_eq!(ContainerRuntime::Podman.command(), "podman");
        assert_eq!(ContainerRuntime::Docker.command(), "docker");
    }

    #[test]
    fn test_invalid_container_name() {
        let runner = ContainerRunner::new("".to_string());
        let result = runner.run("alpine:latest", &["echo", "test"], &[]);
        assert!(matches!(result, Err(ContainerError::InvalidName(_))));
    }

    #[test]
    #[ignore] // Requires podman/docker to be installed
    fn test_run_simple_container() {
        let runner = ContainerRunner::new("test-container-simple".to_string());
        let result = runner.run("alpine:latest", &["echo", "hello"], &[]);

        if let Ok(child) = result {
            let output = child.wait_with_output().unwrap();
            assert!(output.status.success());
        }
    }

    #[test]
    #[ignore] // Requires podman/docker to be installed
    fn test_run_with_input() {
        let runner = ContainerRunner::new("test-container-input".to_string());
        let input = b"hello world";
        let result = runner.run_with_input("alpine:latest", &["cat"], &[], input);

        if let Ok(child) = result {
            let output = child.wait_with_output().unwrap();
            assert!(output.status.success());
            assert_eq!(output.stdout, input);
        }
    }

    #[test]
    fn test_runtime_detect() {
        // This test will pass if either podman or docker is installed
        // It's okay if it fails in environments without container runtimes
        let _ = ContainerRuntime::detect();
    }
}
