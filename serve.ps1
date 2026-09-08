# Minimal static file server for local testing (not part of the app).
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$listener = New-Object System.Net.HttpListener
$listener.Prefixes.Add('http://localhost:8765/')
$listener.Start()
Write-Host "serving $root on http://localhost:8765/"
$types = @{ '.html'='text/html; charset=utf-8'; '.js'='text/javascript; charset=utf-8';
            '.json'='application/manifest+json'; '.png'='image/png' }
while ($listener.IsListening) {
  $ctx = $listener.GetContext()
  $rel = [Uri]::UnescapeDataString($ctx.Request.Url.AbsolutePath.TrimStart('/'))
  if ([string]::IsNullOrWhiteSpace($rel)) { $rel = 'index.html' }
  $path = Join-Path $root $rel
  if ((Test-Path $path -PathType Leaf) -and $path.StartsWith($root)) {
    $ext = [System.IO.Path]::GetExtension($path).ToLower()
    $ctx.Response.ContentType = $(if ($types.ContainsKey($ext)) { $types[$ext] } else { 'application/octet-stream' })
    $bytes = [System.IO.File]::ReadAllBytes($path)
    $ctx.Response.Headers.Add('Cache-Control','no-store')
    $ctx.Response.ContentLength64 = $bytes.Length
    $ctx.Response.OutputStream.Write($bytes, 0, $bytes.Length)
  } else { $ctx.Response.StatusCode = 404 }
  $ctx.Response.Close()
}
