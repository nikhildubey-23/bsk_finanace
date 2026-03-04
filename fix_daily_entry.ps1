$content = @"

             } catch (error) {
                 console.error('Scan error:', error);
                 resultEl.innerHTML = `<div class="alert alert-danger">Error: ${error.message}</div>`;
             } finally {
                 progressEl.style.display = 'none';
                 startBtn.disabled = false;
             }
         }
     </script>
 </body>
 </html>
"@
Add-Content -Path 'c:\Users\Dell\Desktop\BSK_INVESTMENT\templates\daily_entry.html' -Value $content
