vcl 4.0;

# Right now, we hard-code the host address. This should be made dynamic
# through a template or composition of some sort.
backend default {
  .host = "tile_server:8000";
}