"""Geometry validation rules R1-R4 (must pass before resolve_tile)."""
from pipeline.grid import get_char

LAND_CHARS = {"G", "O", "R", "r", "L"}
ROAD_CHARS = {"R", "r"}
SKIP_VALIDATION = {"L"}


def validate_map(grid: list[list[str]]) -> list[str]:
	"""Return list of violation messages (empty = legal)."""
	errors: list[str] = []
	rows = len(grid)
	if rows ==0:
		return errors
	cols = max(len(r) for r in grid)

	for r in range(rows):
		for c in range(cols):
			ch = get_char(grid, r, c)
			if ch in SKIP_VALIDATION:
				continue

			top = get_char(grid, r -1, c)
			bot = get_char(grid, r +1, c)
			lft = get_char(grid, r, c -1)
			rgt = get_char(grid, r, c +1)

			# R1: road cannot directly touch sea
			if ch in ROAD_CHARS:
				for d, nb in [("top", top), ("bottom", bot),
				 ("left", lft), ("right", rgt)]:
					if nb == "S":
						errors.append(
							f"R1 [{r},{c}] '{ch}' road touches sea on {d}; "
							f"roads must be wrapped by land (G/O)."
							)
				# R4: road must connect to another road
				if not any(nb in ROAD_CHARS for nb in (top, bot, lft, rgt)):
					errors.append(
						f"R4 [{r},{c}] '{ch}' road is surrounded by ground "
						f"(no adjacent R/r); roads must connect to other roads."
						)

			# R2: land cannot be1-wide/1-tall peninsula (1x1 island is legal)
			if ch in LAND_CHARS:
				if not (top == "S" and bot == "S" and lft == "S" and rgt == "S"):
					if lft == "S" and rgt == "S":
						errors.append(
							f"R2 [{r},{c}] '{ch}' land has sea on BOTH left and right "
							f"(width=1 peninsula). Land must be >=2 wide here."
							)
					if top == "S" and bot == "S":
						errors.append(
							f"R2 [{r},{c}] '{ch}' land has sea on BOTH top and bottom "
							f"(height=1 peninsula). Land must be >=2 tall here."
							)

			# R3: sea cannot be1-wide/1-tall strait
			if ch == "S":
				if lft in LAND_CHARS and rgt in LAND_CHARS:
					errors.append(
						f"R3 [{r},{c}] 'S' sea has land on BOTH left and right "
						f"(width=1 strait). Sea must be >=2 wide here."
						)
				if top in LAND_CHARS and bot in LAND_CHARS:
					errors.append(
						f"R3 [{r},{c}] 'S' sea has land on BOTH top and bottom "
						f"(height=1 strait). Sea must be >=2 tall here."
						)

	return errors
