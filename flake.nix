{
  description = "fvspec project dev";
  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs";
    parts.url = "github:hercules-ci/flake-parts";
  };
  outputs = { self, nixpkgs, parts, }@inputs:
    parts.lib.mkFlake { inherit inputs; } {
      systems = [ "aarch64-darwin" "x86_64-linux" ];
      perSystem = { system, ... }: {
        devShells.default = let
          pkgs = import inputs.nixpkgs {
            inherit system;
            config.allowUnfree = true;
          };
          name = "fvspec dev";
          buildInputs = with pkgs; [
            elan
            uv
            typst
            typstyle
            nodejs_24
            prettier
            lefthook
            pandoc
            util-linux  # ionice
            claude-code
            ripgrep
          ];
        in pkgs.mkShell { inherit name buildInputs; };
      };
    };
}
