from __future__ import annotations

import io
import json
import unittest
from unittest import mock

import destructive_commands as guard


class DestructiveCommandTests(unittest.TestCase):
    cwd = "/Users/alice/project"
    home = "/Users/alice"

    def assert_denied(self, *commands: str) -> None:
        for command in commands:
            with self.subTest(command=command):
                self.assertIsNotNone(
                    guard.denial_reason(command, cwd=self.cwd, home=self.home)
                )

    def assert_allowed(self, *commands: str) -> None:
        for command in commands:
            with self.subTest(command=command):
                self.assertIsNone(
                    guard.denial_reason(command, cwd=self.cwd, home=self.home)
                )

    def assert_reason(self, expected: str, *commands: str) -> None:
        for command in commands:
            with self.subTest(command=command):
                self.assertEqual(
                    guard.denial_reason(command, cwd=self.cwd, home=self.home),
                    expected,
                )

    def assert_fails_closed(self, *commands: str) -> None:
        self.assert_reason(guard.GENERIC_REASON, *commands)

    def test_denies_protected_rm_targets(self) -> None:
        self.assert_denied(
            "rm -rf /",
            "rm -rf /*",
            "rm -rf ~",
            "rm -rf ~/",
            "rm -rf $HOME",
            'rm -rf "$HOME"',
            "rm -rf ${HOME}",
            "rm -rf /Users",
            "rm -rf /Users/",
            "rm -rf /Users/alice",
            "rm -rf /./Users",
            "rm -rf /tmp/../Users",
            "rm -rf /System",
            "rm -rf /System/Library",
            "rm -rf /System/../System",
            "rm -rf /./*",
            "rm -rf /Users/*",
            "rm -rf $HOME/*",
            "rm -rf ../../alice",
        )

    def test_denies_rm_option_and_operand_variants(self) -> None:
        self.assert_denied(
            "rm -fr /Users",
            "rm -r -f /Users",
            "rm -f -R /Users",
            "rm -rfv /Users",
            "rm --recursive --force /Users",
            "rm --force --recursive /Users",
            "rm -rf -- /Users",
            "rm /Users -rf",
            "rm -rf /tmp /Users",
            "rm -r /System",
            "rm -R /Users",
            "rm --unknown /Users",
        )

    def test_denies_executable_paths_wrappers_and_redirections(self) -> None:
        self.assert_denied(
            "/bin/rm -rf /Users",
            "/usr/bin/rm -rf /Users",
            "command -- rm -rf /Users",
            "env -i rm -rf /Users",
            "env EMPTY=1 rm -rf /Users",
            "sudo -n rm -rf /Users",
            "sudo -- rm -rf /Users",
            "time sudo -n rm -rf /Users",
            "nohup rm -rf /Users",
            ">/tmp/x rm -rf /Users",
            "rm >/tmp/x -rf /Users",
            "rm -rf >/tmp/x /Users",
            "rm 2>/tmp/x -rf /Users",
        )

    def test_denies_control_flow_and_indirect_execution(self) -> None:
        self.assert_denied(
            "echo ok; rm -rf /Users",
            "echo ok && rm -rf /Users",
            "false || rm -rf /Users",
            "printf x | rm -rf /Users",
            "echo ok\nrm -rf /Users",
            "(rm -rf /Users)",
            "{ rm -rf /Users; }",
            "if true; then rm -rf /Users; fi",
            "for item in one; do rm -rf /Users; done",
            "while false; do rm -rf /Users; done",
            "case x in x) rm -rf /Users;; esac",
            "echo $(rm -rf /Users)",
            "echo `rm -rf /Users`",
            "echo <(rm -rf /Users)",
            "sh -c 'rm -rf /Users'",
            "bash -lc 'rm -rf /Users'",
            "zsh -c 'rm -rf /Users'",
            "eval 'rm -rf /Users'",
            "cmd=rm; $cmd -rf /Users",
            "target=/Users; rm -rf \"$target\"",
            "rm -rf \"$unknown_target\"",
            "$unknown_command -rf /Users",
            "cleanup() { rm -rf /Users; }; cleanup",
            "\\\n rm -rf /Users",
            "r\\\nm -rf /Users",
            '"rm" -rf /Users',
            "flags=-rf; rm $flags /Users",
            "rm $unknown_flags /Users",
            "bash -O extglob -c 'rm -rf /Users'",
            "diskutil apfs \"$unknown_verb\" /dev/disk9s2",
            "dd \"$unknown_arguments\"",
            "find -H /System -depth -delete",
            'echo "$(printf safe # )\nrm -rf /Users\n)"',
            'echo "$(case x in x) rm -rf /Users;; esac)"',
            'echo "${ rm -rf /Users; }"',
            'echo "${| rm -rf /Users; }"',
            'echo "${ printf safe # }\nrm -rf /Users\n}"',
        )

    def test_denies_ansi_c_quote_bypasses(self) -> None:
        self.assert_denied(
            "$'rm' -rf /Users",
            "$'\\162\\155' -rf /Users",
            "rm $'-rf' /Users",
            "rm -rf $'/Users'",
            r"printf '%s' $'it\'s text'; rm -rf /Users",
            r"rm -rf /Users; printf '%s' $'it\'s text'",
        )

    def test_denies_disk_formatting_and_erasure(self) -> None:
        self.assert_denied(
            "diskutil eraseDisk APFS Empty GPT /dev/disk9",
            "/usr/sbin/diskutil eraseVolume APFS Empty /dev/disk9s1",
            "diskutil quiet partitionDisk /dev/disk9 GPT APFS Empty 0b",
            "diskutil eraseOptical /dev/disk9",
            "diskutil zeroDisk /dev/disk9",
            "diskutil randomDisk /dev/disk9",
            "diskutil secureErase 0 /dev/disk9",
            "diskutil apfs deleteContainer /dev/disk9s2",
            "diskutil apfs deleteVolume /dev/disk9s2",
            "diskutil coreStorage delete UUID",
            "diskutil apfs eraseVolume /dev/disk9s2 -name Empty",
            "diskutil apfs deleteVolumeGroup UUID",
            "diskutil apfs deleteSnapshot /dev/disk9s2 -xid 1",
            "diskutil mergePartitions JHFS+ New disk1s1 disk1s2",
            "diskutil splitPartition disk1s1 JHFS+ A 50% JHFS+ B 50%",
            "diskutil resizeVolume disk1s1 10g",
            "diskutil apfs resizeContainer disk1s1 10g",
            "mkfs /dev/example",
            "/sbin/mkfs.ext4 /dev/example",
            "newfs_apfs /dev/example",
            "mke2fs /dev/example",
            "wipefs -a /dev/example",
            "blkdiscard /dev/example",
            "gpt destroy /dev/disk9",
            "dd if=/tmp/image of=/dev/disk9",
            "find /System -depth -delete",
            "newfs /dev/example",
            "gpt -f destroy /dev/disk9",
            "cat /tmp/image > /dev/disk9",
            "cp /tmp/image /dev/disk9",
            "tee /dev/disk9",
            "printf safe > /dev/disk?",
            "tee /dev/disk?",
            "cp /tmp/image /dev/disk?",
            "cat /tmp/image > /dev/mapper/system",
        )

    def test_denies_opaque_expansion_and_state_bypasses(self) -> None:
        self.assert_denied(
            "rm ${UNSET_ARGS:--rf /Users}",
            "args='-rf /Users'; rm $args",
            "target='/Users /tmp'; rm -rf $target",
            "cleanup() { rm $1; }; cleanup '-rf /Users'",
            "/bin/r[m] -rf /Users",
            "cmd='rm -rf /Users'; $cmd",
            "rm -rf /tmp/*/../../Users",
            "target=/Users; if false; then target=/tmp; fi; rm -rf \"$target\"",
            "cmd=rm; if false; then cmd=echo; fi; $cmd -rf /Users",
            "target=/Users; false && target=/tmp; rm -rf \"$target\"",
            "target=/Users; (target=/tmp); rm -rf \"$target\"",
            "target=/Users; printf safe | target=/tmp; rm -rf \"$target\"",
            "target=/tmp; set_target() { target=/Users; }; set_target; rm -rf \"$target\"",
            "target=/tmp; eval 'target=/Users'; rm -rf \"$target\"",
            "args=(rm -rf /Users); $args",
            "target=/Users; target\\=/tmp; rm -rf \"$target\"",
            "target=/Users; t\"arget\"=/tmp; rm -rf \"$target\"",
            "target=/U; target+=sers; rm -rf \"$target\"",
            "target=; : ${target:=/Users}; rm -rf \"$target\"",
            "target=/tmp; read target <<< /Users; rm -rf \"$target\"",
            "target=/tmp; printf -v target /Users; rm -rf \"$target\"",
        )

    def test_denies_opaque_shell_and_dispatch_paths(self) -> None:
        self.assert_denied(
            "bash <<< 'rm -rf /Users'",
            "printf '%s' 'rm -rf /Users' | bash",
            "sh /tmp/opaque-script",
            "nice rm -rf /Users",
            "noglob rm -rf /Users",
            "nocorrect rm -rf /Users",
            "coproc rm -rf /Users",
            "printf '%s' /Users | xargs rm -rf",
            "find /Users -exec rm -rf {} +",
            "find /Users -exec sh -c 'rm -rf /Users' \\;",
            "find /Users -exec /bin/r[m] -rf {} +",
            "sudo X=1 rm -rf /Users",
            "sudo -n X=1 /bin/rm -rf /Users",
            "trap 'rm -rf /Users' EXIT",
            "trap 'rm -rf /Users' 0",
            "bash -c \"trap -- 'rm -rf /Users' EXIT\"",
            "alias wipe='rm -rf'\nwipe /Users",
            "alias -g WIPE='; rm -rf /Users'\nprintf safe WIPE",
            "${UNSET_SHELL:-sh} -c 'rm -rf /Users'",
            "nice -- rm -rf /Users",
            "- rm -rf /Users",
            "chroot / rm -rf Users",
            "sudo chroot / rm -rf Users",
            "chroot / sh -c 'rm -rf /Users'",
            "doas rm -rf /Users",
        )

    def test_denies_cwd_case_and_critical_root_bypasses(self) -> None:
        self.assert_denied(
            "cd /Users; rm -rf alice",
            "cd /; rm -rf Users",
            "cd /; rm -rf \"$PWD\"",
            "target=~; rm -rf \"$target\"",
            "/bin/RM -rf /Users",
            "/USR/BIN/RM -rf /users",
            "rm -rf /SYSTEM",
            "rm -rf /users/ALICE",
            "rm -rf /Library",
            "rm -rf /Applications",
            "rm -rf /usr",
            "rm -rf /private",
            "rm -rf /etc",
            "rm -rf /var",
            "rm -rf /home",
            "rm -rf /root",
            "rm -rf /usr/bin",
            "env --chdir=/ rm -rf Users",
            "env -C / rm -rf Users",
            "sudo -D / rm -rf Users",
            "sudo --chdir=/ rm -rf Users",
            "env -C ~ rm -rf .",
            "env --chdir ~ rm -rf .",
            "sudo -D ~ rm -rf .",
            "sudo --chdir ~ rm -rf .",
            "env -C ~/.. rm -rf alice",
            "sudo -D ~/.. rm -rf alice",
            "env -C /Use?s rm -rf alice",
            "sudo -D /Use?s rm -rf alice",
        )

    def test_allows_benign_removal_boundaries(self) -> None:
        self.assert_allowed(
            "rm -rf /tmp/build",
            "rm -rf /Users/alice/project/build",
            'rm -rf "$HOME/project/.cache"',
            "rm -rf ~/project/.cache",
            "rm -f /Users",
            "rm -r /tmp/build",
            "rm -rf",
            "rm -rf -- /tmp/build",
            "find /tmp/build -depth -delete",
            "dd if=/tmp/image of=/tmp/copy",
        )

    def test_allows_shell_text_used_only_as_data(self) -> None:
        self.assert_allowed(
            "echo 'rm -rf /Users'",
            "printf '%s' 'rm -rf /Users'",
            "git commit -m 'rm -rf /Users'",
            "python3 -c 'print(\"rm -rf /Users\")'",
            "example='rm -rf /Users'",
            "examples=(rm -rf /Users)",
            "alias cleanup='rm -rf /Users'",
            "cleanup() { rm -rf /Users; }",
            "function cleanup { rm -rf /Users; }",
            "function cleanup\n{ rm -rf /Users; }",
            "$'rm -rf /Users'",
            "$'echo ok\\nrm -rf /Users'",
        )

    def test_allows_literal_expansions_and_operators(self) -> None:
        self.assert_allowed(
            "rm -rf '~'",
            'rm -rf "~"',
            "rm -rf '$HOME'",
            r'rm -rf "\$HOME"',
            "rm -rf '/*'",
            "rm -rf /\\*",
            "printf '%s' ';' rm -rf /Users",
            "printf '%s' '|' rm -rf /Users",
            "printf '%s' \\; rm -rf /Users",
            "echo '$HOME /*'",
            "echo '$(rm -rf /Users)'",
            r'echo "\$(rm -rf /Users)"',
            "echo '`rm -rf /Users`'",
            'case x in "rm -rf /Users") printf safe;; esac',
            "cat <<< 'rm -rf /Users'",
            "rm -rf *",
            "rm -rf ?",
            "cat <(printf safe)",
            "diff <(printf a) <(printf b)",
            "rm -rf /tmp/{a,b}",
            "rm -rf /tmp/{1..3}",
            r'''echo "$(printf '%s' $'it\'s safe')"''',
            "echo \"$(cat <<'EOF'\n)\nEOF\n)\"",
        )

    def test_ignores_comments_and_non_executable_heredoc_data(self) -> None:
        self.assert_allowed(
            "echo ok # ; rm -rf /Users",
            "echo ok # $(rm -rf /Users)",
            "# rm -rf /Users",
            "# rm -rf /Users; diskutil eraseDisk APFS X /dev/example\nprintf safe",
            "cat <<'EOF'\nrm -rf /Users\nEOF\n",
            "cat <<EOF\nrm -rf /Users\nEOF\n",
            "cat <<EOF; printf safe\nrm -rf /Users\nEOF\n",
            "cat <<'EOF'\n$(rm -rf /Users)\nEOF",
            "cat <<-'EOF'\n\trm -rf /Users\nEOF",
            "cat <<$'EOF'\nrm -rf /Users\nEOF",
            "cat <<\"E\\\"OF\"\nrm -rf /Users\nE\"OF",
            "examples=( # $(rm -rf /Users)\n safe)",
        )

    def test_checks_executable_heredoc_regions(self) -> None:
        self.assert_denied(
            "cat <<EOF\n$(rm -rf /Users)\nEOF\n",
            "bash <<'EOF'\nrm -rf /Users\nEOF\n",
            "sh <<EOF\nrm -rf /Users\nEOF\n",
        )

    def test_allows_benign_disk_commands_and_similar_names(self) -> None:
        self.assert_allowed(
            "diskutil list",
            "diskutil verifyDisk /dev/disk9",
            "printf '%s' mkfs.ext4",
            "mkfs-helper /tmp/example",
            "diskutility eraseDisk",
        )

    def test_fails_closed_on_malformed_or_ambiguous_shell(self) -> None:
        self.assert_fails_closed(
            "echo 'unterminated",
            "echo trailing\\",
            "echo $(unfinished",
            "cat <<EOF\nmissing terminator",
            "echo \0",
            "eval \"$unknown\"",
            "sh -c \"$unknown\"",
            "$'\\162\\155\\0junk' -rf /Users",
            "rm -rf $'/Users\\0/junk'",
            'echo "${ { :; }; rm -rf /Users; }"',
            'cat /tmp/image > "$UNKNOWN_TARGET"',
            'tee "$UNKNOWN_TARGET" < /tmp/image',
            "alias -g WIPE='/tmp/x; rm -rf /Users'\nprintf safe > WIPE",
            "alias -g '>=; rm -rf /Users; : >'\nprintf safe > /tmp/x",
        )

    def test_fails_closed_on_malformed_shell_structures(self) -> None:
        self.assert_fails_closed(
            "{",
            "}",
            "(",
            ")",
            "if true; then",
            "case x in",
            "for x in",
            "while true; do",
            "{ printf safe;",
            "(printf safe",
            "printf safe )",
        )

    def test_reports_specific_reasons_for_understood_commands(self) -> None:
        self.assert_reason(guard.USERS_REASON, "rm -rf /Users")
        self.assert_reason(guard.HOME_REASON, "rm -rf /Users/alice")
        self.assert_reason(guard.SYSTEM_REASON, "rm -rf /System/Library")
        self.assert_reason(guard.DISK_REASON, "diskutil eraseDisk APFS X /dev/disk9")

    def test_shared_analysis_budget_fails_closed(self) -> None:
        alias_body = "printf safe;" * 4_000
        command = "alias work='" + alias_body + "'\n" + "work\n" * 20
        self.assertIsNotNone(
            guard.denial_reason(command, cwd=self.cwd, home=self.home)
        )


class HookProtocolTests(unittest.TestCase):
    class BrokenInput:
        def __init__(self, error: Exception) -> None:
            self.error = error

        def read(self, *_args: object, **_kwargs: object) -> str:
            raise self.error

    def invoke(self, input_text: str) -> str:
        return self.invoke_stream(io.StringIO(input_text))

    def invoke_stream(self, stdin: object) -> str:
        stdout = io.StringIO()
        with mock.patch.object(guard.sys, "stdin", stdin), mock.patch.object(
            guard.sys, "stdout", stdout
        ):
            guard.main()
        return stdout.getvalue()

    def test_safe_command_emits_nothing(self) -> None:
        payload = json.dumps({"tool_input": {"command": "printf '%s' safe"}})
        self.assertEqual(self.invoke(payload), "")

    def test_empty_command_emits_nothing(self) -> None:
        payload = json.dumps({"tool_input": {"command": ""}})
        self.assertEqual(self.invoke(payload), "")

    def test_unicode_command_emits_nothing(self) -> None:
        payload = json.dumps({"tool_input": {"command": "printf 'café'"}})
        self.assertEqual(self.invoke(payload), "")

    def test_payload_workdir_is_used_for_relative_targets(self) -> None:
        payload = json.dumps(
            {"tool_input": {"command": "rm -rf .", "workdir": "/Users/alice"}}
        )
        output = json.loads(self.invoke(payload))
        self.assertEqual(output["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_relative_payload_workdir_fails_closed(self) -> None:
        payload = json.dumps(
            {"tool_input": {"command": "printf safe", "workdir": "relative"}}
        )
        output = json.loads(self.invoke(payload))
        self.assertEqual(output["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_blocked_command_emits_native_pre_tool_use_shape(self) -> None:
        payload = json.dumps({"tool_input": {"command": "rm -rf /Users"}})
        output = json.loads(self.invoke(payload))
        self.assertEqual(
            output,
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": guard.USERS_REASON,
                }
            },
        )

    def test_malformed_payloads_fail_closed(self) -> None:
        malformed = (
            "",
            " ",
            "{",
            "not json",
            "null",
            "[]",
            "{}",
            '{"tool_input": null}',
            '{"tool_input": {}}',
            '{"tool_input": []}',
            '{"tool_input": {"command": null}}',
            '{"tool_input": {"command": 1}}',
            '{"tool_input": {"command": []}}',
            '{"tool_input": {"command": {}}}',
            '{"tool_input": {"command": "safe"}} trailing',
        )
        for payload in malformed:
            with self.subTest(payload=payload):
                output = json.loads(self.invoke(payload))
                self.assertEqual(
                    output["hookSpecificOutput"]["permissionDecision"], "deny"
                )

    def test_input_stream_errors_fail_closed(self) -> None:
        for error in (UnicodeError("bad input"), OSError("bad input")):
            with self.subTest(error=type(error).__name__):
                output = json.loads(self.invoke_stream(self.BrokenInput(error)))
                self.assertEqual(
                    output["hookSpecificOutput"]["permissionDecision"], "deny"
                )

    def test_unexpected_parser_failure_fails_closed(self) -> None:
        payload = json.dumps({"tool_input": {"command": "printf safe"}})
        with mock.patch.object(guard, "denial_reason", side_effect=RuntimeError):
            output = json.loads(self.invoke(payload))
        self.assertEqual(output["hookSpecificOutput"]["permissionDecision"], "deny")


if __name__ == "__main__":
    unittest.main()
