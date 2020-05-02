class SimpleHTMLBody():
	def __init__(self, title: str, h1: str, p: str):
		self.title = f"<title>{title}</title>"
		self.h1 = f"<h1>{h1}</h1>"
		self.p = f"<p>{p}</p>"
		self.head = f"<head>{self.title}</head>"
		self.body = f"<body>{self.h1}\n{self.p}</body>"
		self.html = f"<html>{self.head}\n{self.body}</html>"

	def __str__(self):
		return self.html

class HTMLResponse200(SimpleHTMLBody):
	def __init__(self):
		self.title = "OK"
		self.h1 = self.title
		self.p = "Any static content could be provided here"
		super().__init__(self.title, self.h1, self.p)

class HTMLResponse429(SimpleHTMLBody):
	def __init__(self, max_requests):
		self.title = "Too Many Requests"
		self.h1 = self.title
		self.p = f"We only allow {max_requests} requests per minute. Try again soon."
		super().__init__(self.title, self.h1, self.p)

