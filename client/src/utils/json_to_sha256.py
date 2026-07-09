import json
import hashlib


def json_to_sha256(json_data: dict) -> str:
    """
    Converts a Python dictionary (from JSON) to a unique SHA-256 hash.

    The function creates a canonical string representation of the JSON by
    sorting the keys and removing whitespace. This ensures that two
    semantically identical JSON objects will produce the same hash, regardless
    of key order or formatting.

    Args:
        json_data: A Python dictionary representing the JSON object.

    Returns:
        A string containing the hexadecimal SHA-256 hash of the JSON data.
    """
    # Convert the dictionary to a string in a canonical format.
    # sort_keys=True ensures that the keys are always in the same order.
    # separators=(',', ':') removes whitespace for a more compact representation.
    canonical_string = json.dumps(json_data, sort_keys=True, separators=(",", ":"))

    # Encode the string to bytes, as hashing functions operate on bytes.
    # UTF-8 is a standard encoding.
    encoded_string = canonical_string.encode("utf-8")

    # Create a SHA-256 hash object.
    hasher = hashlib.sha256()

    # Update the hash object with the bytes of the canonical string.
    hasher.update(encoded_string)

    # Return the hexadecimal representation of the hash.
    return hasher.hexdigest()
