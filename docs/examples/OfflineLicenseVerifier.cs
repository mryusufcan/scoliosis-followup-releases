// Reference-only C# verifier for Scoliosis Follow-Up.
// NuGet: BouncyCastle.Cryptography
// The client contains only the public key. Never ship the issuer private key.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Text.RegularExpressions;
using Org.BouncyCastle.Crypto;
using Org.BouncyCastle.Crypto.Parameters;
using Org.BouncyCastle.Crypto.Signers;
using Org.BouncyCastle.OpenSsl;
using Org.BouncyCastle.X509;

public sealed record VerifiedLicense(
    string LicenseId,
    string CustomerRef,
    IReadOnlyList<string> Features,
    DateTimeOffset ExpiresAt,
    string? MaxAppVersion);

public static class OfflineLicenseVerifier
{
    private const string ExpectedFormat = "ScoliosisFollowUpOfflineLicenseV1";
    private const string ExpectedProduct = "ScoliosisFollowUp";
    private static readonly Regex VersionPattern = new("^(\\d+)\\.(\\d+)(?:\\.(\\d+))?(?:[-+].*)?$", RegexOptions.Compiled);

    public static VerifiedLicense Verify(
        string licenseJson,
        string publicKeyPem,
        string deviceFingerprint,
        string appVersion,
        DateTimeOffset? now = null,
        TimeSpan? clockSkew = null)
    {
        using var document = JsonDocument.Parse(licenseJson);
        var root = document.RootElement;
        if (root.ValueKind != JsonValueKind.Object)
            throw new InvalidDataException("Lisans nesne biçiminde olmalıdır.");

        RequireString(root, "format", ExpectedFormat);
        RequireString(root, "product", ExpectedProduct);
        var licenseId = RequiredString(root, "license_id");
        var customerRef = RequiredString(root, "customer_ref");
        var binding = RequiredString(root, "device_binding");
        var signatureText = RequiredString(root, "signature");
        var issuedAt = ParseUtc(root, "issued_at");
        var expiresAt = ParseUtc(root, "expires_at");
        var features = RequiredStringArray(root, "features");
        var maxAppVersion = OptionalString(root, "max_app_version");

        var signature = Base64UrlDecode(signatureText);
        var canonicalUnsignedPayload = CanonicalizeWithoutSignature(root);
        var publicKey = LoadEd25519PublicKey(publicKeyPem);
        var verifier = new Ed25519Signer();
        verifier.Init(false, publicKey);
        verifier.BlockUpdate(canonicalUnsignedPayload, 0, canonicalUnsignedPayload.Length);
        if (!verifier.VerifySignature(signature))
            throw new InvalidDataException("Lisans imzası doğrulanamadı.");

        var current = (now ?? DateTimeOffset.UtcNow).ToUniversalTime();
        var skew = clockSkew ?? TimeSpan.FromMinutes(5);
        if (expiresAt <= issuedAt || current + skew < issuedAt || current - skew >= expiresAt)
            throw new InvalidDataException("Lisans zaman aralığı geçersiz veya süresi dolmuş.");
        if (!CryptographicOperations.FixedTimeEquals(
                Encoding.ASCII.GetBytes(binding), Encoding.ASCII.GetBytes(deviceFingerprint)))
            throw new InvalidDataException("Lisans bu cihaza bağlı değil.");
        if (!VersionAllowed(appVersion, maxAppVersion))
            throw new InvalidDataException("Uygulama sürümü lisans kapsamı dışında.");

        return new VerifiedLicense(licenseId, customerRef, features, expiresAt, maxAppVersion);
    }

    private static AsymmetricKeyParameter LoadEd25519PublicKey(string pem)
    {
        using var reader = new StringReader(pem);
        var keyObject = new PemReader(reader).ReadObject();
        if (keyObject is not AsymmetricKeyParameter key || key.IsPrivate)
            throw new InvalidDataException("Public key bekleniyordu.");
        return key;
    }

    // This canonicalizer sorts object keys recursively and emits compact UTF-8 JSON.
    // The issuer must use the identical canonicalization rules. For production,
    // standardize on RFC 8785/JCS or a tested shared canonicalization library.
    private static byte[] CanonicalizeWithoutSignature(JsonElement root)
    {
        using var stream = new MemoryStream();
        using (var writer = new Utf8JsonWriter(stream, new JsonWriterOptions { Indented = false }))
        {
            WriteCanonicalObjectWithoutSignature(writer, root);
        }
        return stream.ToArray();
    }

    private static void WriteCanonicalObjectWithoutSignature(Utf8JsonWriter writer, JsonElement root)
    {
        writer.WriteStartObject();
        foreach (var property in root.EnumerateObject()
                     .Where(property => property.Name != "signature")
                     .OrderBy(property => property.Name, StringComparer.Ordinal))
        {
            writer.WritePropertyName(property.Name);
            WriteCanonicalValue(writer, property.Value);
        }
        writer.WriteEndObject();
    }

    private static void WriteCanonicalValue(Utf8JsonWriter writer, JsonElement value)
    {
        switch (value.ValueKind)
        {
            case JsonValueKind.Object:
                writer.WriteStartObject();
                foreach (var property in value.EnumerateObject().OrderBy(p => p.Name, StringComparer.Ordinal))
                {
                    writer.WritePropertyName(property.Name);
                    WriteCanonicalValue(writer, property.Value);
                }
                writer.WriteEndObject();
                break;
            case JsonValueKind.Array:
                writer.WriteStartArray();
                foreach (var item in value.EnumerateArray()) WriteCanonicalValue(writer, item);
                writer.WriteEndArray();
                break;
            default:
                value.WriteTo(writer);
                break;
        }
    }

    private static string RequiredString(JsonElement root, string name)
    {
        if (!root.TryGetProperty(name, out var value) || value.ValueKind != JsonValueKind.String)
            throw new InvalidDataException($"{name} alanı eksik veya geçersiz.");
        var text = value.GetString();
        if (string.IsNullOrWhiteSpace(text)) throw new InvalidDataException($"{name} alanı boş.");
        return text;
    }

    private static string? OptionalString(JsonElement root, string name)
    {
        if (!root.TryGetProperty(name, out var value) || value.ValueKind == JsonValueKind.Null) return null;
        return value.ValueKind == JsonValueKind.String ? value.GetString() : throw new InvalidDataException($"{name} alanı geçersiz.");
    }

    private static void RequireString(JsonElement root, string name, string expected)
    {
        if (RequiredString(root, name) != expected) throw new InvalidDataException($"{name} alanı beklenen değer değil.");
    }

    private static IReadOnlyList<string> RequiredStringArray(JsonElement root, string name)
    {
        if (!root.TryGetProperty(name, out var value) || value.ValueKind != JsonValueKind.Array)
            throw new InvalidDataException($"{name} listesi geçersiz.");
        return value.EnumerateArray().Select(item => item.GetString() ?? throw new InvalidDataException($"{name} öğesi geçersiz.")).ToArray();
    }

    private static DateTimeOffset ParseUtc(JsonElement root, string name)
    {
        var value = RequiredString(root, name);
        if (!DateTimeOffset.TryParse(value, CultureInfo.InvariantCulture, DateTimeStyles.RoundtripKind, out var parsed))
            throw new InvalidDataException($"{name} alanı geçersiz.");
        return parsed.ToUniversalTime();
    }

    private static byte[] Base64UrlDecode(string text)
    {
        var normalized = text.Replace('-', '+').Replace('_', '/');
        normalized += new string('=', (4 - normalized.Length % 4) % 4);
        try { return Convert.FromBase64String(normalized); }
        catch (FormatException ex) { throw new InvalidDataException("İmza Base64URL biçiminde değil.", ex); }
    }

    private static bool VersionAllowed(string appVersion, string? maxVersion)
    {
        if (string.IsNullOrWhiteSpace(maxVersion) || maxVersion is "*" or "any") return true;
        var app = ParseVersion(appVersion);
        if (maxVersion.EndsWith(".x", StringComparison.OrdinalIgnoreCase))
        {
            var prefix = maxVersion[..^2].Split('.').Select(int.Parse).ToArray();
            return app.Take(prefix.Length).SequenceEqual(prefix);
        }
        return Compare(app, ParseVersion(maxVersion)) <= 0;
    }

    private static (int Major, int Minor, int Patch) ParseVersion(string value)
    {
        var match = VersionPattern.Match(value.Trim());
        if (!match.Success) throw new InvalidDataException($"Sürüm geçersiz: {value}");
        return (int.Parse(match.Groups[1].Value), int.Parse(match.Groups[2].Value), int.Parse(match.Groups[3].Success ? match.Groups[3].Value : "0"));
    }

    private static int Compare((int Major, int Minor, int Patch) left, (int Major, int Minor, int Patch) right) =>
        left.Major != right.Major ? left.Major.CompareTo(right.Major) :
        left.Minor != right.Minor ? left.Minor.CompareTo(right.Minor) : left.Patch.CompareTo(right.Patch);
}
