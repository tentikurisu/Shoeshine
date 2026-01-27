terraform {
  backend "s3" {
    bucket         = "shoeshine-terraform-state"
    key            = "shoeshine/terraform.tfstate"
    region         = "eu-west-2"
    dynamodb_table = "terraform-locks"
    encrypt        = true
  }
}
