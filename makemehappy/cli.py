import argparse

ap = argparse.ArgumentParser()

### Top Level Options #########################################################

ap.add_argument(
    "-d", "--directory", default = None,
    help = "specify the build-root directory")

ap.add_argument(
    "-m", "--module", default = "module.yaml",
    help = "specify the file that contains the" +
           " module description (defaults to module.yaml)")

ap.add_argument(
    "-y", "--system", default = "system.yaml",
    dest = 'system_spec',
    help = "specify the file that contains the" +
           " system description (defaults to system.yaml)")

ap.add_argument(
    "-p", "--preserve", action = "store_true",
    help = "preserve build root instead of deleting it." +
           " In combination with -d, delete build root"  +
           " before termination.")

ap.add_argument(
    "-q", "--quiet", action = "store_true",
    help = "Disable informational output")

ap.add_argument(
    "-R", "--raise-exceptions", action = "store_true",
    help = "Raise toplevel exceptions in case of errors.")

ap.add_argument(
    "-P", "--show-phases", action = "store_true",
    help = "Show build phases even with --log-to-file.")

ap.add_argument(
    "-L", "--log-all", action = "store_true",
    help = "send all output to logging facility")

ap.add_argument(
    "-l", "--log-to-file", action = "store_true",
    help = "log output to file (implies --log-all)")

ap.add_argument(
    "-f", "--log-file", default = None,
    help = "specify log-file name to use")

ap.add_argument(
    "-T", "--toolchains", default = None,
    help = "select toolchains to include in build")

ap.add_argument(
    "-B", "--buildtools", default = None,
    help = "select buildtools to include in build")

ap.add_argument(
    "-C", "--buildconfigs", default = None,
    help = "select build configurations to include in build")

ap.add_argument(
    "-A", "--architectures", default = None,
    help = "select architectures to include in build")

ap.add_argument(
    "-Q", "--query", default = None,
    help = "query aspects about the program")

ap.add_argument(
    "-c", "--config", default = [], action = "append",
    help = "add configuration to config-stack")

ap.add_argument(
    "-U", "--disable-user-directory",
    default = False, action = "store_true",
    help = "disable use of files in user-configuration directory")

ap.add_argument(
    "-r", "--revision", default = [], action = "append",
    help = "add a revision-override specification")

ap.add_argument(
    "-s", "--source", default = [], action = "append",
    help = "add a module source definition")

ap.add_argument(
    "-S", "--succeed", action = "store_true",
    help = "force successful termination")

ap.add_argument(
    "-e", "--environment-overrides", action = "store_true",
    help = "allow mmh to override existing environment variables")

ap.add_argument(
    "-E", "--ignore-dep-errors", action = "store_true",
    help = "ignore errors in dependency evaluation")

ap.add_argument(
    "-V", "--version", action = "store_true",
    help = "show program version")

ap.add_argument(
    "-v", "--verbose", action = "store_true",
    help = "produce verbose output")

ap.add_argument(
    "--load-insecure-files", action = "store_true",
    help = "load world-writeable files that contain code")

### Top-Level Commands

subp = ap.add_subparsers(
    dest = 'sub_command', metavar = 'Sub Commands')

# build
ap_build = subp.add_parser('build', help = 'Build a module in many instances')
ap_build.add_argument('instances', default = [ ], nargs = '*')

# init
ap_init = subp.add_parser(
    'build-tree-init', aliases = [ 'init' ],
    help = 'Build a module')

ap_init.set_defaults(sub_command = 'build-tree-init')

# download
ap_download = subp.add_parser(
    'download-source', aliases = [ 'get' ],
    help = 'Download sources for a module')

ap_download.set_defaults(sub_command = 'download-source')
ap_download.add_argument(
    "-b", "--bare",
    dest = 'clone_bare',
    default = False,
    action = 'store_true',
    help = "Create bare git repository when downloading source")
ap_download.add_argument(
    "-r", "--release",
    dest = 'use_release',
    default = False,
    action = 'store_true',
    help = "Use latest release tag after cloning")
ap_download.add_argument('modules', nargs = '+')

# download-sources
ap_sources = subp.add_parser(
    'download-sources',
    help = 'Download sources for ALL module')
ap_sources.add_argument(
    "-b", "--bare",
    dest = 'clone_bare',
    default = False,
    action = 'store_true',
    help = "Create bare git repository when downloading source")
ap_sources.add_argument('destination', nargs = '?', default = '.')

# dump-description
ap_dump = subp.add_parser(
    'dump-description', aliases = [ 'dump' ],
    help = 'Show parsed instruction file data')

ap_dump.set_defaults(sub_command = 'dump-description')

# fetch-dependencies
ap_fetch = subp.add_parser(
    'fetch-dependencies', aliases = [ 'deps' ],
    help = 'Download dependencies of a module')

ap_fetch.set_defaults(sub_command = 'fetch-dependencies')

# generate-toplevel
ap_top = subp.add_parser(
    'generate-toplevel', aliases = [ 'top' ],
    help = 'Generate toplevel of module build-tree')

ap_top.set_defaults(sub_command = 'generate-toplevel')

# focus-instance
ap_focus = subp.add_parser(
    'focus-instance', aliases = [ 'focus' ],
    help = "Focus a module instance's build-tree")

ap_focus.set_defaults(sub_command = 'focus-instance')
ap_focus.add_argument('instance', nargs = 1)
ap_focus.add_argument(
    "-l", "--link-name", default = 'focus',
    help = "Change name of created symlink")
ap_focus.add_argument(
    "-n", "--no-compile-commands", action = 'store_true',
    help = "Inhibit symlinking compile_commands.json")

# prepare
ap_prepare = subp.add_parser(
    'prepare',
    help = 'Generate toplevel of module build-tree')

# revision-overrides
ap_revisions = subp.add_parser(
    'revision-overrides', aliases = [ 'revs' ],
    help = 'Show and test revision overrides')

ap_revisions.set_defaults(sub_command = 'revision-overrides')
ap_revisions.add_argument('modules', nargs = '*')

# list-instances
ap_list = subp.add_parser(
    'list-instances', aliases = [ 'list' ],
    help = 'List instances available in build-tree')

ap_list.set_defaults(sub_command = 'list-instances')

# run-instance
ap_run = subp.add_parser(
    'run-instance', aliases = [ 'run' ],
    help = '(Re)run previously configured build-tree')

ap_run.set_defaults(sub_command = 'run-instance')
ap_run.add_argument('instances', nargs = '*')

# show-result
ap_result = subp.add_parser(
    'show-result', aliases = [ 'result' ],
    help = 'Show result table from log-file')

ap_result.set_defaults(sub_command = 'show-result')
ap_result.add_argument(
    "-f", "--full", action = "store_true",
    dest = 'full_result',
    help = "Replay full log with log-prefix stripped.")
ap_result.add_argument(
    "-g", "--grep", action = "store_true",
    dest = 'grep_result',
    help = "Scan log for incidents.")
ap_result.add_argument(
    "-j", "--json", action = "store_true",
    dest = 'json_incidents',
    help = "Report incidents from log file in JSON format.")
ap_result.add_argument(
    "-r", "--report", action = "store_true",
    dest = 'report_incidents',
    help = "Report incidents from log file.")
ap_result.add_argument(
    "-p", "--paged", action = "store_true",
    dest = 'use_pager',
    help = "Use pager to view result.")
ap_result.add_argument(
    "-q", "--quiet", action = "store_true",
    dest = 'quiet_result',
    help = "Do not show any result output.")
ap_result.add_argument(
    "-s", "--short", action = "store_true",
    dest = 'short_result',
    help = "Only show final short-form result.")
ap_result.add_argument('file', nargs = 1)

# show-source
ap_show = subp.add_parser(
    'show-source', aliases = [ 'show' ],
    help = 'Show source location for module(s)')

ap_show.set_defaults(sub_command = 'show-source')
ap_show.add_argument('modules', nargs = '*')

# verify
ap_verify = subp.add_parser(
    'verify', help = 'Verify checksum data')
ap_verify.add_argument(
    "-b", "--basename", default = 'contents',
    help = "Basename for checksum files in directories")
ap_verify.add_argument(
    "-r", "--root-directory", default = '.',
    help = "Root directory for files in checksum files")
ap_verify.add_argument('sources', nargs = '*')

# system
ap_system = subp.add_parser(
    'system', help = 'Handle building production systems')

ap_system.set_defaults(sub_command = 'system')
ap_system.add_argument(
    "-s", "--single-instance", action = "store_true",
    help = "Build a single instance in the build directory root")
ap_system.add_argument(
    "-c", "--no-combinations", action = "store_true",
    help = "Do not build any combinations")


### System Commands

sub_system = ap_system.add_subparsers(
    dest = 'system', metavar = 'System Commands')

# list
sys_list = sub_system.add_parser(
    'list', help = 'List all specified build instances')

# db
sys_db = sub_system.add_parser(
    'db', help = 'Link compile command db to system root')

sys_db.add_argument(
    "-l", "--location", default = '.',
    help = "specify the build-root directory")
sys_db.add_argument('instances', default = [ ], nargs = '*')

# build
sys_build = sub_system.add_parser(
    'build', help = 'Build all or specified build instances')
sys_build.add_argument(
    "-f", "--force-build", action = "store_true",
    help = "force all build phases")
sys_build.add_argument('instances', default = [ ], nargs = '*')

# rebuild
sys_rebuild = sub_system.add_parser(
    'rebuild', help = 'Rebuild all or specified build instances')

sys_rebuild.add_argument('instances', default = [ ], nargs = '*')

# clean
sys_clean = sub_system.add_parser(
    'clean', help = 'Clean all or specified build instances')

sys_clean.add_argument('instances', default = [ ], nargs = '*')

# combinations
sys_combinations = sub_system.add_parser(
    'combinations', aliases = [ 'com' ],
    help = 'Inspect system combination builds')

sys_combinations.add_argument(
    "-c", "--cleanup-outputs", action = 'store_true',
    help = "Remove combination outputs")

sys_combinations.add_argument(
    "-C", "--cleanup-dubious", action = 'store_true',
    help = "Remove combination outputs that are not fully intact")

sys_combinations.add_argument(
    "-g", "--garbage-collect", action = 'store_true',
    help = "Remove stale combination outputs")

sys_combinations.add_argument(
    "-l", "--list-combinations", action = 'store_true',
    help = "List directories containing combination data")

sys_combinations.add_argument(
    "-L", "--list-outputs", action = 'store_true',
    help = "List files generated by combinations")

sys_combinations.add_argument(
    "-q", "--query-combinations", action = 'store_true',
    help = "Query specified combinations")

sys_combinations.add_argument(
    "-p", "--pattern", action = 'append',
    help = "Select output names by pattern")

sys_combinations.add_argument(
    "-x", "--exclude", action = 'append',
    help = "Exclude output names by pattern")

sys_combinations.add_argument(
    "-j", "--json", action = 'store_true',
    help = "Produce JSON output instead of terminal markup")

sys_combinations.add_argument('instances', default = [ ], nargs = '*')

# deploy
sys_deploy = sub_system.add_parser(
    'deploy', help = 'Run system deployment sub-system')

sys_deploy.add_argument(
    "-S", "--strict", action = 'store_true',
    help = "Make all manifest issues into errors")

sys_deploy.add_argument(
    "-s", "--show", action = 'store_true',
    help = "Show human readable manifest spec")

sys_deploy.add_argument(
    "-k", "--keep", action = 'store_true',
    help = "Do not remove destination directory before deployment")

sys_deploy.add_argument(
    "-l", "--list", action = 'store_true', dest = 'listCollection',
    help = "List input/output file collection of manifest")

sys_deploy.add_argument('destination', default = 'deploy', nargs = '?')

### End of Argument Parser Spec
