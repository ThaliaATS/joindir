import fnmatch
import sys
from pathlib import Path
from tkinter import Tk, filedialog

import pyperclip
from prompt_toolkit import Application, prompt
from prompt_toolkit.data_structures import Point
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import HSplit, Layout, Window
from prompt_toolkit.layout.controls import FormattedTextControl


CONFIG_DIR = Path(__file__).resolve().parent / "config"
CONFIG_FILES = {
	"extensions": CONFIG_DIR / "extensoes.txt",
	"ignored_folders": CONFIG_DIR / "ignorar_pastas.txt",
	"ignored_suffixes": CONFIG_DIR / "ignorar_finais.txt",
	"ignored_files": CONFIG_DIR / "ignorar_arquivos.txt",
}


def ensure_configuration_files():
	CONFIG_DIR.mkdir(exist_ok=True)

	for file_path in CONFIG_FILES.values():
		file_path.touch(exist_ok=True)


def load_list(file_path: Path):
	return [
		line.strip()
		for line in file_path.read_text(encoding="utf-8").splitlines()
		if line.strip()
	]


def save_list(file_path: Path, values):
	values.sort(key=str.casefold)
	content = "\n".join(values)
	file_path.write_text(f"{content}\n" if content else "", encoding="utf-8")


def normalize_extension(value: str) -> str:
	value = value.strip()

	if not value:
		return value

	if not value.startswith("."):
		value = f".{value}"

	return value.casefold()


def normalize_plain(value: str) -> str:
	return value.strip()


NORMALIZERS = {
	"extensions": normalize_extension,
	"ignored_folders": normalize_plain,
	"ignored_suffixes": normalize_plain,
	"ignored_files": normalize_plain,
}


def load_configuration():
	ensure_configuration_files()

	return {
		"extensions": {
			normalize_extension(value)
			for value in load_list(CONFIG_FILES["extensions"])
		},
		"ignored_folders": {
			value.casefold()
			for value in load_list(CONFIG_FILES["ignored_folders"])
		},
		"ignored_suffixes": tuple(
			value.casefold()
			for value in load_list(CONFIG_FILES["ignored_suffixes"])
		),
		"ignored_files": {
			value.casefold()
			for value in load_list(CONFIG_FILES["ignored_files"])
		},
	}


def choose_folder():
	root = Tk()
	root.withdraw()
	root.attributes("-topmost", True)
	folder = filedialog.askdirectory(title="Escolha uma pasta")
	root.destroy()
	return Path(folder) if folder else None


def choose_output_file():
	root = Tk()
	root.withdraw()
	root.attributes("-topmost", True)

	file_name = filedialog.asksaveasfilename(
		title="Salvar copia.txt",
		initialfile="copia.txt",
		defaultextension=".txt",
		filetypes=[("Arquivo de texto", "*.txt")],
	)

	root.destroy()
	return Path(file_name) if file_name else None


def load_gitignore_patterns(folder: Path):
	"""Lê um .gitignore na raiz da pasta escolhida, se existir.

	Suporte simplificado: não trata negações ("!padrao") nem todas as
	regras da especificação oficial, mas cobre o caso comum de nomes
	de pasta/arquivo e padrões simples com curinga (*, ?).
	"""
	gitignore = folder / ".gitignore"

	if not gitignore.exists():
		return []

	patterns = []

	for line in gitignore.read_text(encoding="utf-8", errors="ignore").splitlines():
		line = line.strip()

		if not line or line.startswith("#") or line.startswith("!"):
			continue

		patterns.append(line.strip("/"))

	return patterns


def matches_gitignore(relative_parts, patterns):
	if not patterns:
		return False

	relative_str = "/".join(relative_parts).casefold()

	for pattern in patterns:
		pattern = pattern.casefold()

		if any(fnmatch.fnmatch(part.casefold(), pattern) for part in relative_parts):
			return True

		if fnmatch.fnmatch(relative_str, pattern) or fnmatch.fnmatch(
			relative_str, f"*/{pattern}"
		):
			return True

	return False


def scan_folder(folder: Path, known_files: set[Path], configuration, gitignore_patterns=None):
	found_files = []
	gitignore_patterns = gitignore_patterns or []

	try:
		walker = folder.rglob("*")

		while True:
			try:
				file_path = next(walker)
			except StopIteration:
				break
			except PermissionError as error:
				print(f"\nAviso: acesso negado, pulando: {error.filename}")
				continue

			if not file_path.is_file():
				continue

			if any(
				part.casefold() in configuration["ignored_folders"]
				for part in file_path.parts
			):
				continue

			name = file_path.name.casefold()

			if name in configuration["ignored_files"]:
				continue

			if any(name.endswith(suffix) for suffix in configuration["ignored_suffixes"]):
				continue

			if file_path.suffix.casefold() not in configuration["extensions"]:
				continue

			if gitignore_patterns:
				relative_parts = file_path.relative_to(folder).parts

				if matches_gitignore(relative_parts, gitignore_patterns):
					continue

			file_path = file_path.resolve()

			if file_path in known_files:
				continue

			known_files.add(file_path)
			found_files.append(file_path)
	except OSError as error:
		print(f"\nAviso: erro ao ler a pasta ({error}). Resultado pode estar incompleto.")

	return sorted(found_files, key=lambda item: str(item).casefold())


def read_file(file_path: Path):
	"""Retorna o conteúdo do arquivo, ou None se não foi possível ler."""
	try:
		return file_path.read_text(encoding="utf-8")
	except UnicodeDecodeError:
		try:
			return file_path.read_text(encoding="latin-1", errors="replace")
		except OSError:
			return None
	except OSError:
		return None


def generate_text(files):
	parts = []
	failed_files = []

	for file_path in files:
		content = read_file(file_path)

		if content is None:
			failed_files.append(file_path)
			content = ""

		parts.extend((str(file_path), "", content, ""))

	return "\n".join(parts), failed_files


def request_value():
	try:
		value = prompt("Novo valor: ").strip()
	except (EOFError, KeyboardInterrupt):
		return None

	return value or None


def edit_configuration_list(title: str, file_path: Path, normalizer=normalize_plain):
	values = load_list(file_path)
	values.sort(key=str.casefold)
	cursor = 0

	def render_body():
		if not values:
			return "Nenhum valor.\n"

		return "\n".join(
			f"{'→ ' if index == cursor else '  '}{value}"
			for index, value in enumerate(values)
		)

	def render_footer():
		current = values[cursor] if values else "-"
		return (
			f"\n\n{title}: {len(values)} | Atual: {current}\n"
			"--------------------------------\n\n"
			"[↑↓] mover  [A] adiciona  [E] editar  "
			"[Del/Backspace] remover  [Esc] voltar"
		)

	def get_cursor_position():
		return Point(x=0, y=cursor)

	control = FormattedTextControl(
		lambda: render_body() + render_footer(),
		get_cursor_position=get_cursor_position,
	)
	bindings = KeyBindings()

	@bindings.add("up")
	def move_up(event):
		nonlocal cursor
		if cursor > 0:
			cursor -= 1

	@bindings.add("down")
	def move_down(event):
		nonlocal cursor
		if cursor < len(values) - 1:
			cursor += 1

	@bindings.add("a")
	def add_value(event):
		event.app.exit(result="add")

	@bindings.add("e")
	def edit_value(event):
		if values:
			event.app.exit(result="edit")

	@bindings.add("delete")
	@bindings.add("backspace")
	def remove_value(event):
		nonlocal cursor
		if not values:
			return

		values.pop(cursor)
		save_list(file_path, values)
		cursor = min(cursor, max(0, len(values) - 1))

	@bindings.add("escape")
	@bindings.add("c-c")
	def leave_editor(event):
		event.app.exit(result="back")

	app = Application(
		layout=Layout(HSplit([Window(control, always_hide_cursor=True)])),
		key_bindings=bindings,
		full_screen=True,
	)

	while True:
		result = app.run()

		if result == "add":
			value = request_value()

			if value is not None:
				value = normalizer(value)

				if value:
					values.append(value)
					save_list(file_path, values)
					cursor = values.index(value)

			continue

		if result == "edit":
			value = request_value()

			if value is not None and values:
				value = normalizer(value)

				if value:
					values[cursor] = value
					save_list(file_path, values)
					cursor = values.index(value)

			continue

		return


def select_menu(options, header: str = "", footer_hint: str = "[↑↓] mover  [Enter] selecionar  [Esc] voltar"):
	"""Menu navegável por setas em tela cheia.

	options: lista de tuplas (rótulo, valor). Retorna o valor escolhido,
	ou None se o usuário cancelar (Esc / Ctrl+C).
	"""
	cursor = 0

	def render_body():
		return "\n".join(
			f"{'→ ' if index == cursor else '  '}{label}"
			for index, (label, _value) in enumerate(options)
		)

	def render():
		parts = []

		if header:
			parts.append(header)

		parts.append(render_body())
		parts.append("")
		parts.append(footer_hint)
		return "\n".join(parts)

	def get_cursor_position():
		offset = header.count("\n") + 1 if header else 0
		return Point(x=0, y=offset + cursor)

	control = FormattedTextControl(render, get_cursor_position=get_cursor_position)
	bindings = KeyBindings()

	@bindings.add("up")
	def move_up(event):
		nonlocal cursor
		if cursor > 0:
			cursor -= 1

	@bindings.add("down")
	def move_down(event):
		nonlocal cursor
		if cursor < len(options) - 1:
			cursor += 1

	@bindings.add("enter")
	def confirm(event):
		event.app.exit(result=options[cursor][1])

	@bindings.add("escape")
	@bindings.add("c-c")
	def cancel(event):
		event.app.exit(result=None)

	app = Application(
		layout=Layout(HSplit([Window(control, always_hide_cursor=True)])),
		key_bindings=bindings,
		full_screen=True,
	)

	return app.run()


def edit_configurations():
	config_map = {
		"extensions": ("Extensões", CONFIG_FILES["extensions"], NORMALIZERS["extensions"]),
		"ignored_folders": ("Pastas ignoradas", CONFIG_FILES["ignored_folders"], NORMALIZERS["ignored_folders"]),
		"ignored_suffixes": ("Finais ignorados", CONFIG_FILES["ignored_suffixes"], NORMALIZERS["ignored_suffixes"]),
		"ignored_files": ("Arquivos ignorados (nome exato)", CONFIG_FILES["ignored_files"], NORMALIZERS["ignored_files"]),
	}
	menu_options = [(label, key) for key, (label, _path, _norm) in config_map.items()]

	while True:
		choice = select_menu(menu_options, header="Editar configurações\n")

		if choice is None:
			return

		title, file_path, normalizer = config_map[choice]
		edit_configuration_list(title, file_path, normalizer)


def file_interface(files, known_files, configuration):
	cursor = 0

	def render_body():
		if not files:
			return "Nenhum arquivo.\n"

		return "\n".join(
			f"{'→ ' if index == cursor else '  '}{file_path}"
			for index, file_path in enumerate(files)
		)

	def render_footer():
		current = files[cursor].name if files else "-"
		return (
			f"\n\nArquivos: {len(files)} | Atual: {current}\n"
			"[↑↓] mover  [Del/Backspace] remover  "
			"[A] adicionar pasta  [Enter] copiar  [Esc] sair"
		)

	def get_cursor_position():
		return Point(x=0, y=cursor)

	control = FormattedTextControl(
		lambda: render_body() + render_footer(),
		get_cursor_position=get_cursor_position,
	)
	bindings = KeyBindings()

	@bindings.add("up")
	def move_up(event):
		nonlocal cursor
		if cursor > 0:
			cursor -= 1

	@bindings.add("down")
	def move_down(event):
		nonlocal cursor
		if cursor < len(files) - 1:
			cursor += 1

	@bindings.add("delete")
	@bindings.add("backspace")
	def remove_file(event):
		nonlocal cursor
		if not files:
			return

		files.pop(cursor)
		cursor = min(cursor, max(0, len(files) - 1))

	@bindings.add("a")
	def add_folder(event):
		event.app.exit(result="add")

	@bindings.add("enter")
	def confirm(event):
		event.app.exit(result="ok")

	@bindings.add("escape")
	@bindings.add("c-c")
	def cancel(event):
		event.app.exit(result="cancel")

	app = Application(
		layout=Layout(HSplit([Window(control, always_hide_cursor=True)])),
		key_bindings=bindings,
		full_screen=True,
	)

	while True:
		result = app.run()

		if result == "add":
			folder = choose_folder()

			if folder:
				gitignore_patterns = load_gitignore_patterns(folder)
				files.extend(
					scan_folder(folder, known_files, configuration, gitignore_patterns)
				)
				files.sort(key=lambda item: str(item).casefold())

			continue

		return result


def finish(files):
	text, failed_files = generate_text(files)
	estimated_tokens = len(text) // 4

	choice = select_menu(
		[
			("Copiar para área de transferência", "copy"),
			("Salvar como copia.txt", "save"),
			("Cancelar", "cancel"),
		],
		header=f"Arquivos selecionados: {len(files)}\n",
	)

	if choice == "copy":
		pyperclip.copy(text)
		print("\nConteúdo copiado para a área de transferência!")
	elif choice == "save":
		destination = choose_output_file()

		if not destination:
			print("Operação cancelada.")
			return

		destination.write_text(text, encoding="utf-8")
		print(f"\nArquivo salvo em:\n{destination}")
	else:
		print("Cancelado.")
		return

	print(f"\nArquivos          : {len(files)}")
	print(f"Caracteres        : {len(text):,}")
	print(f"Tamanho           : {len(text) / 1024:.1f} KB")
	print(f"Tokens (estimado) : ~{estimated_tokens:,}")

	if failed_files:
		print(f"\nAviso: {len(failed_files)} arquivo(s) não puderam ser lidos e ficaram vazios:")
		for file_path in failed_files:
			print(f"  - {file_path}")


def generate_file(preset_folder: Path = None):
	configuration = load_configuration()
	folder = preset_folder or choose_folder()

	if not folder:
		return

	gitignore_patterns = load_gitignore_patterns(folder)

	if gitignore_patterns:
		print(f"\n.gitignore encontrado em {folder} — aplicando {len(gitignore_patterns)} padrão(ões).")

	known_files = set()
	files = scan_folder(folder, known_files, configuration, gitignore_patterns)
	result = file_interface(files, known_files, configuration)

	if result != "ok":
		print("Cancelado.")
		return

	finish(files)


def wellcome():
	return r"""
    .---.   .-'''-.                                          
    |   |  '   _    \               _______                  
    '---'/   /` '.   \ .--.  _..._  \  ___ `'.   .--.        
    .---.   |     \  ' |__|.'     '. ' |--.\  \  |__|        
    |   |   '      |  '.--.   .-.   .| |    \  ' .--.-,.--.  
    |   \    \     / / |  |  '   '  || |     |  '|  |  .-. | 
    |   |`.   ` ..' /  |  |  |   |  || |     |  ||  | |  | | 
    |   |   '-...-'`   |  |  |   |  || |     ' .'|  | |  | | 
    |   |              |  |  |   |  || |___.' /' |  | |  '-  
    |   |              |__|  |   |  /_______.'/  |__| |      
 __.'   '                 |  |   |  \_______|/      | |      
|      '                  |  |   |  |               |_|      
|____.'                   '--'   '--'                        

    Criado por: Thalia Linda & Maravilhosa
    Versão: 1.260725v
"""


def main():
	ensure_configuration_files()

	preset_folder = None

	if len(sys.argv) > 1:
		candidate = Path(sys.argv[1])

		if candidate.is_dir():
			preset_folder = candidate
		else:
			print(f"\nAviso: '{sys.argv[1]}' não é uma pasta válida. Ignorando.")

	if preset_folder is not None:
		generate_file(preset_folder=preset_folder)
		input("\nPressione Enter para continuar...")

	while True:
		choice = select_menu(
			[
				("Gerar arquivo", "generate"),
				("Editar configurações", "edit"),
				("Sair", "exit"),
			],
			header=wellcome(),
		)

		if choice == "generate":
			generate_file()
		elif choice == "edit":
			edit_configurations()
		else:
			return


if __name__ == "__main__":
	main()
