# Only the ruleset bundled with tflint: no plugin download, works offline.
plugin "terraform" {
  enabled = true
  preset  = "recommended"
}
