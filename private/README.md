This directory is reserved for sensitive data such as API keys,
credentials or logs that you do not want to commit to version
control.  By default the application does not read anything from
this folder; it simply exists as a placeholder so that secrets can
be mounted into the container at runtime.

**Do not** commit real secrets here.  Instead, reference this folder
in your `.gitignore` and copy files into it on deployment if
required.  For example, you might mount a file containing your
OpenAI API key and then adjust `config/settings.py` to read it.