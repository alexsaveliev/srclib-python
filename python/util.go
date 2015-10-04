package python

import (
	"crypto/sha1"
	"encoding/hex"
	"log"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
)

var dockerEnv = os.Getenv("IN_DOCKER_CONTAINER")

func runCmdLogError(cmd *exec.Cmd) {
	log.Printf("Running %v", cmd.Args)
	err := runCmdStderr(cmd)
	if err != nil {
		log.Printf("Error running `%s`: %s", strings.Join(cmd.Args, " "), err)
	}
}

func runCmdStderr(cmd *exec.Cmd) error {
	cmd.Stderr = os.Stderr
	cmd.Stdout = os.Stderr
	return cmd.Run()
}

// getProgramPath returns path to toolchain (assuming that exe file is located in .bin, path is <path-to-.bin>/..
// In `docker` mode, it will return empty string because there is no virtualenv.
func getProgramPath() (string, error) {
	if dockerEnv == "" {
		path := filepath.Join(filepath.Dir(os.Args[0]), "..")
		return filepath.Abs(path)
	}
	return "", nil
}

// getVENVBinPath returns toolchains Python virtualenv path. If toolchain is ran in
// `docker` mode, it will return empty string because there is no virtualenv.
func getVENVBinPath() (string, error) {
	if dockerEnv == "" {
		path, err := getProgramPath()
		if err != nil {
			return "", err
		}
		return filepath.Abs(filepath.Join(path, ".env", getEnvBinDir()))
	}
	return "/venv/bin", nil
}

// Returns binaries directory of virtualenv which may be different on Windows and Unix
func getEnvBinDir() string {
	if runtime.GOOS == "windows" {
		return "Scripts"
	} else {
		return "bin"
	}
}

func getHash(text string) string {
	hasher := sha1.New()
	hasher.Write([]byte(text))
	return hex.EncodeToString(hasher.Sum(nil))[:8]
}
