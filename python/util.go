package python

import (
	"log"
	"os"
	"os/exec"
	"path/filepath"
	"strings"

	"sourcegraph.com/sourcegraph/toolchain"
)

func runCmdLogError(cmd *exec.Cmd) {
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

func getVENVBinPath() (string, error) {
	if os.Getenv("IN_DOCKER_CONTAINER") == "" {
		tc, err := toolchain.Lookup("sourcegraph.com/sourcegraph/srclib-python")
		if err != nil {
			return "", err
		}
		return filepath.Join(tc.Dir, ".env", "bin"), nil
	}
	return "", nil
}
