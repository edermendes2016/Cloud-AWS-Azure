variable "region" {
  description = "AWS region of the state backend."
  type        = string
  default     = "us-east-1"
}

variable "state_bucket" {
  description = "Name of the S3 bucket that stores Terraform state."
  type        = string
}

variable "lock_table" {
  description = "Name of the DynamoDB table used for state locking."
  type        = string
}

variable "emulator" {
  description = "True when the target is a local emulator (relaxes credential checks only)."
  type        = bool
  default     = false
}

variable "enforce_tls" {
  description = "Attach the bucket policy that denies non-TLS requests. Disable only for HTTP emulators."
  type        = bool
  default     = true
}

variable "tags" {
  description = "Standard tags applied to every resource."
  type        = map(string)
}
