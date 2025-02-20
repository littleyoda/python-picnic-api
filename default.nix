{ pkgs ? import <nixpkgs> {} }:
  pkgs.mkShell {
    nativeBuildInputs = with pkgs; [
      python313
      python313Packages.poetry-core
      python313Packages.black
      python313Packages.flake8
      python313Packages.python-dotenv
      python313Packages.requests
      ruff
    ];
}
