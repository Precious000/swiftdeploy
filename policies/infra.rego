package swiftdeploy.infra

import future.keywords.if
import future.keywords.contains

# OPA evaluates this entire package when asked about infra decisions.
# The CLI sends host stats as input. OPA checks them against data.json thresholds.

default allow = false

# allow is true only when there are zero violations
allow if {
    count(violations) == 0
}

# violations is a SET of human-readable denial reasons
violations contains msg if {
    input.disk_free_gb < data.thresholds.min_disk_free_gb
    msg := sprintf(
        "Disk too full: %.1fGB free, need %.1fGB",
        [input.disk_free_gb, data.thresholds.min_disk_free_gb]
    )
}

violations contains msg if {
    input.cpu_load > data.thresholds.max_cpu_load
    msg := sprintf(
        "CPU load too high: %.2f, limit is %.2f",
        [input.cpu_load, data.thresholds.max_cpu_load]
    )
}
