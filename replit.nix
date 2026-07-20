{pkgs}: {
  deps = [
    pkgs.wkhtmltopdf
    pkgs.libdrm
    pkgs.libGL
    pkgs.mesa
    pkgs.xorg.libX11
    pkgs.pango
    pkgs.cairo
    pkgs.xorg.libXrandr
    pkgs.xorg.libXfixes
    pkgs.xorg.libXdamage
    pkgs.xorg.libXcomposite
    pkgs.xorg.libXext
    pkgs.at-spi2-atk
    pkgs.alsa-lib
    pkgs.libxkbcommon
    pkgs.cups
    pkgs.atk
    pkgs.dbus
    pkgs.glib
    pkgs.nss
    pkgs.nspr
  ];
}
