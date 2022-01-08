vcl 4.0;

# Right now, we hard-code the host address. This should be made dynamic
# through a template or composition of some sort.
backend default {
  .host = "tile_server:8000";
}

sub vcl_deliver {
    if (obj.hits > 0) { # Add debug header to see if it's a HIT/MISS and the number of hits, disable when not needed
        set resp.http.X-Cache = "hit";
    } else {
        set resp.http.X-Cache = "miss";
    }
}