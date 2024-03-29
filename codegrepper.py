#!/usr/bin/python3

# Pure python, self-contained implementation of a very basics SAST tool
# Created by d3adc0de
# 
# Credits: https://endler.dev/awesome-static-analysis/

import re
import os
import argparse
import sys
from pathlib import Path
import traceback
import time
from colorama import Fore


class LogLevel(object):
    UNKNOWN = -1
    DEBUG = 0
    INFO = 1
    WARNING = 2
    ERROR = 2

    @staticmethod
    def to_s(level):
        if level == LogLevel.DEBUG:
            return "DEBUG"
        elif level == LogLevel.INFO:
            return "INFO"
        elif level == LogLevel.WARNING:
            return "WARNING"
        elif level == LogLevel.ERROR:
            return "ERROR"
        else:
            return "UNKNOWN"


class Logger(object):
    def __init__(self, filename=None):
        self.log_file = filename if filename else "debug.log"

    @staticmethod
    def logging(message, level=None):
        if not level:
            level = LogLevel.UNKNOWN
        print(f"[{level}][{time.time()}]: {message}")

    def log(self, message, level=None):
        time_tag = time.strftime('%Y%m%d%H%M%S', time.localtime())
        if not level:
            level = LogLevel.INFO
        try:
            with open(self.log_file, "a") as _log:
                _log.write(
                    f"[{time_tag}][{LogLevel.to_s(level)}]: {message.encode(errors='ignore')}\n")
        except Exception as e:
            print(e)
            pass

    def info(self, message):
        self.log(message, LogLevel.INFO)

    def warn(self, message):
        self.log(message, LogLevel.WARNING)

    def error(self, message):
        self.log(message, LogLevel.ERROR)


class CodeGrepper:
    TEXTCHARS = ''.join(map(chr, [7, 8, 9, 10, 12, 13, 27] + list(range(0x20, 0x100))))

    def __init__(self, category=None, subcategory=None, filter=None, case_insensitive=False, advanced_filter=None,
                 exclude_comments=False, debug=False, context=None, files_only=False, relative_paths=False, no_regex=False):
        self.signatures = self.init_signatures(category, subcategory)
        self.category = category
        self.subcategory = subcategory
        self.advanced_filter = advanced_filter
        if exclude_comments:
            self.exclude_comments()
        self.case_insensitive = case_insensitive
        self.forward_context = 0
        self.backward_context = 0
        self.parse_context(context)
        self.files_only = files_only
        self.relative_paths = relative_paths
        self.dont_show_regex = no_regex
        self.highlight = ["", ""]
        self.filter = [filter] if filter else ["php", "rb", "js", "java", "pl", "phtml", "cs", "c", "cpp", "xml",
                                               "config", "ini", "sql", "pas"]
        self.exclude = ["png", "jpg", "jpeg", "gif", "woff", "svg", "woff2", "tiff", "mp3"]
        self.debug = debug
        self.logger = Logger() if debug else None

    def parse_context(self, context):
        if not context:
            return
        plus = re.search(r"\+\s*\d+", context)
        minus = re.search(r"-\s*\d+", context)
        if plus:
            self.forward_context = int(plus[0].replace("+", "").strip()) + 1
        if minus:
            self.backward_context = int(minus[0].replace("-", "").strip())

    @staticmethod
    def is_binary(filepath):
        try:
            with open(filepath, "rb").read(1024) as lookup:
                return bool(bytes.translate(None, CodeGrepper.TEXTCHARS.encode()))
        except Exception as e:
            # print(e) // Causing the __enter__ bug
            return False

    def exclude_comments(self):
        sig = self.init_signatures(category=self.category)
        if "comments" in sig.keys():
            self.advanced_filter["exclude-regexes"] += sig["comments"]

    def is_included(self, path):
        if not self.advanced_filter:
            return True
        if len(self.advanced_filter["include-directory"]) > 0:
            for f in self.advanced_filter["include-directory"]:
                regex = re.compile(f, re.IGNORECASE)
                if regex.search(path):
                    return True
            return False
        elif len(self.advanced_filter["exclude-directory"]) > 0:
            for f in self.advanced_filter["exclude-directory"]:
                regex = re.compile(f, re.IGNORECASE)
                if regex.search(path):
                    return False
            return True
        else:
            return True

    def regex_excluded(self, mo):
        if not self.advanced_filter:
            return False
        if len(self.advanced_filter["exclude-regexes"]) > 0:
            for f in self.advanced_filter["exclude-regexes"]:
                pattern = re.compile(f)
                if pattern.search(f"{mo.group()}"):
                    return True
            return False
        else:
            return False

    def is_filtered(self, file_path):
        name, ext = os.path.splitext(file_path)
        if ext.replace(".", "") in self.filter:
            return True
        else:
            return False

    def audit(self, directory=".", regex=None):
        if directory:
            directory = str(Path(directory).resolve())
        if regex is None:
            if isinstance(self.signatures, list):
                for regex in self.signatures:
                    self.search(directory=directory, regex=regex, category=self.category, subcategory=self.subcategory)
            elif isinstance(self.signatures, dict):
                for category in self.signatures.keys():
                    for regex in self.signatures[category]:
                        self.search(directory=directory, regex=regex, category=self.category, subcategory=category)
            else:
                pass
        else:
            self.search(directory, regex)

    def search(self, directory=".", regex=None, category=None, subcategory=None):
        if self.debug:
            self.logger.info(f"[*] Start searching")
        pattern = re.compile(regex, re.IGNORECASE) if self.case_insensitive else re.compile(regex)

        for path, _, files in os.walk(directory):
            if self.debug:
                self.logger.info(f"Searching within {path}")

            if not self.is_included(path):
                continue
            # for skip in [x for x in _ if not self.is_included(x)]:
            #     _.remove(skip)

            for fn in files:
                file_path = os.path.join(path, fn)
                if self.debug:
                    self.logger.info(f"Analysing {file_path}")

                if self.is_binary(file_path):
                    if self.debug:
                        self.logger.info(f"Binary File: {file_path}")
                    continue
                if not self.is_filtered(file_path):
                    if self.debug:
                        self.logger.info(f"Filtered File: {file_path}")
                    continue
                try:
                    if self.debug:
                        self.logger.info(f"Grepping file: {file_path}")

                    with open(file_path, "r", errors="ignore") as handle:
                        lines = handle.readlines()
                        lineno = 0
                        display_path = file_path if not self.relative_paths else Path(
                            file_path).relative_to(Path(directory)).as_posix()

                        # for lineno, line in enumerate(handle):
                        for line in lines:
                            mo = pattern.search(line)
                            if mo:
                                if self.regex_excluded(mo):
                                    # print("Skipping")
                                    continue
                                msg = ""

                                if category:
                                    if not self.dont_show_regex:
                                        msg += f"[{Fore.BLUE}{category}{Fore.WHITE}][{Fore.BLUE}{subcategory}{Fore.WHITE}]{Fore.MAGENTA}{display_path}{Fore.WHITE}"
                                    else:
                                        msg += f"{Fore.MAGENTA}{display_path}{Fore.WHITE}"
                                else:
                                    if not self.dont_show_regex:
                                        msg += f"[{Fore.BLUE}custom{Fore.WHITE}]{Fore.MAGENTA}{display_path}{Fore.WHITE}"
                                    else:
                                        msg += f"{Fore.MAGENTA}{display_path}{Fore.WHITE}"

                                if self.files_only:
                                    print(msg)
                                    break

                                show = line.strip().replace(
                                    mo.group(),
                                    f"{Fore.RED}{mo.group()}{Fore.WHITE}")

                                if self.forward_context + self.backward_context == 0:
                                    msg += f":{Fore.GREEN}{lineno}{Fore.WHITE}: {show}"
                                else:
                                    show = "".join([f"{_ln}: {lines[_ln]}" if _ln != lineno else f"{_ln}: {Fore.RED}{lines[_ln]}{Fore.WHITE}" for _ln in range(
                                        lineno-self.backward_context, lineno+self.forward_context
                                    )])
                                    msg += f"\n{show}"
                                print(msg)
                            lineno += 1
                except Exception as e:
                    if self.debug:
                        self.logger.error(f"Exception: {e}")
                    print("[-] Error opening file: {}".format(file_path))

    def init_signatures(self, category=None, subcategory=None):
        signatures = {
            "dotnet": {
                "cookies": [
                    r"System.Net.Cookie",
                    r"HTTPOnly",
                    r"document.cookie"
                ],
                "crypto": [
                    r"RNGCryptoServiceProvider",
                    r"SHA",
                    r"MD5",
                    r"base64",
                    r"xor",
                    r"\([\s]*DES|TripleDES|DES[\s]*\)",
                    r"(RC2|RC4)",
                    r"System.Random",
                    r"Random",
                    r"System.Security.Cryptography",
                    r"PBEParameterSpec",
                    r"PasswordDeriveBytes"
                ],
                "error": [
                    r"catch[\s]*\{",
                    r"Finally",
                    r"trace",
                    r"enabled",
                    r"customErrors",
                    r"mode"
                ],
                "inputcontrols": [
                    r"system.web.ui.htmlcontrols.htmlinputhidden",
                    r"system.web.ui.webcontrols.hiddenfield",
                    r"system.web.ui.webcontrols.hyperlink",
                    r"system.web.ui.webcontrols.textbox",
                    r"system.web.ui.webcontrols.label",
                    r"system.web.ui.webcontrols.linkbutton",
                    r"system.web.ui.webcontrols.listbox",
                    r"system.web.ui.webcontrols.checkboxlist",
                    r"system.web.ui.webcontrols.dropdownlist"
                ],
                "legacy": [
                    r"printf",
                    r"strcpy"
                ],
                "logging": [
                    r"log4net",
                    r"Console.WriteLine",
                    r"System.Diagnostics.Debug",
                    r"System.Diagnostics.Trace"
                ],
                "memory": [
                    r"MemoryStream",
                    r".Write",
                    r".Read",
                    r".WriteByte",
                    r".WriteTo",
                    r".WriteAsync",
                    r".Flush",
                    r".Finalize",
                    r".CopyTo"
                ],
                "permission": [
                    r".RequestMinimum",
                    r".RequestOptional",
                    r"Assert",
                    r"Debug.Assert",
                    r"CodeAccessPermission",
                    r"ReflectionPermission.MemberAccess",
                    r"SecurityPermission.ControlAppDomain",
                    r"SecurityPermission.UnmanagedCode",
                    r"SecurityPermission.SkipVerification",
                    r"SecurityPermission.ControlEvidence",
                    r"SecurityPermission.SerializationFormatter",
                    r"SecurityPermission.ControlPrincipal",
                    r"SecurityPermission.ControlDomainPolicy",
                    r"SecurityPermission.ControlPolicy"
                ],
                "reflection": [
                    r"Reflection"
                ],
                "request": [
                    r"parameter",
                    r"white-list.",
                    r"request.accepttypes",
                    r"request.browser",
                    r"request.files",
                    r"request.headers",
                    r"request.httpmethod",
                    r"request.item",
                    r"request.querystring",
                    r"request.form",
                    r"request.cookies",
                    r"request.certificate",
                    r"request.rawurl",
                    r"request.servervariables",
                    r"request.url",
                    r"request.urlreferrer",
                    r"request.useragent",
                    r"request.userlanguages",
                    r"request.IsSecureConnection",
                    r"request.TotalBytes",
                    r"request.BinaryRead",
                    r"InputStream",
                    r"HiddenField.Value",
                    r"TextBox.Text",
                    r"recordSet"
                ],
                "serialization": [
                    r"Serialization",
                    r"SerializationFormatter",
                    r"Serializable",
                    r"SerializeObject",
                    r"SerializationBinder",
                    r"SimpleTypeResolver",
                    r"Json.Net",
                    r"ToObject",
                    r"ReadObject",
                    r"YamlDotNet",
                    r"JsonSerializerSettings",
                    r"TypeNameHandling.All",
                    r"DeserializeObject\s*\(",
                    r"Deserialize\s*\(",
                    r"ISerializable",
                    r"(Json|JavaScript|Xml|(Net)*DataContract)Serializer",
                    r"(Binary|ObjectState|Los|Soap)Formatter"
                ],
                "deserialization": [
                    r"[^\w]*(JavaScript|Xml)Serializer",
                    r"SimpleTypeResolver",
                    r"ToObject[\s]*\(",
                    r"ReadObject[\s]*\(",
                    r"TypeNameHandling.All",
                    r"DeserializeObject[\s]*\(",
                    r"Deserialize[\s]*\("
                ],
                "sqlstrings": [
                    r"SELECT.*WHERE",
                    r"INSERT.*VALUES\(",
                    r"(OR|AND).*(LIKE|=|<|>|!)",
                ],
                "sql": [
                    r"exec\s*sp_executesql",
                    r"execute\s*sp_executesql",
                    r"exec\s*sp_",
                    r"execute\s*sp_",
                    r"exec\s*xp_",
                    r"execute\s*sp_",
                    r"exec\s*@",
                    r"execute\s*@",
                    r"executestatement",
                    r"executeSQL",
                    r"setfilter",
                    r"executeQuery",
                    r"GetQueryResultInXML",
                    r"adodb",
                    r"sqloledb",
                    r"sql\s*server",
                    r"driver",
                    r"Server\.CreateObject",
                    r"\.Provider",
                    r"\.Open",
                    r"ADODB.recordset",
                    r"New\s*OleDbConnection",
                    r"ExecuteReader",
                    r"DataSource",
                    r"SqlCommand",
                    r"Microsoft.Jet",
                    r"SqlDataReader",
                    r"ExecuteReader",
                    r"GetString",
                    r"SqlDataAdapter",
                    r"CommandType",
                    r"StoredProcedure",
                    r"System\.Data\.sql"
                ],
                "ssl": [
                    r"ServerCertificateValidationCallback",
                    r"checkCertificateName",
                    r"checkCertificateRevocationList"
                ],
                "xss": [
                    r"response.write",
                    r"<%\s*=",
                    r"HttpUtility",
                    r"HtmlEncode",
                    r"UrlEncode",
                    r"innerText",
                    r"innerHTML"
                ]
            },
            "java": {
                "exceptions": [
                    r"AccessControlException",
                    r"BindException",
                    r"ConcurrentModificationException",
                    r"DigestException",
                    r"FileNotFoundException",
                    r"GeneralSecurityException",
                    r"InsufficientResourcesException",
                    r"InvalidAlgorithmParameterException",
                    r"InvalidKeyException",
                    r"InvalidParameterException",
                    r"JarException",
                    r"KeyException",
                    r"KeyManagementException",
                    r"KeyStoreException",
                    r"NoSuchAlgorithmException",
                    r"NoSuchProviderException",
                    r"NotOwnerException",
                    r"NullPointerException",
                    r"OutOfMemoryError",
                    r"PriviledgedActionException",
                    r"ProviderException",
                    r"SignatureException",
                    r"SQLException",
                    r"StackOverflowError",
                    r"UnrecoverableEntryException",
                    r"UnrecoverableKeyException"
                ],
                "java": [
                    r"AccessController",
                    r"addHeader",
                    r"CallableStatement",
                    r"Cipher",
                    r"controller",
                    r"createRequest",
                    r"doPrivileged",
                    r"exec[\s]*\(",
                    r"executeQuery[\s]*\(",
                    r"executeUpdate",
                    r"getParameter[\s]*\(",
                    r"getProperty",
                    r"getQueryString[\s]*\(",
                    r"getSession[\s]\(",
                    r"HTTPCookie",
                    r"HttpServletRequest",
                    r"HttpServletResponse",
                    r"HttpsURLConnection",
                    r"invalidate",
                    r"IS_SUPPORTING_EXTERNAL_ENTITIES",
                    r"KeyManagerFactory",
                    r"PreparedStatement",
                    r"random",
                    r"java.util.Random",
                    r"SecureRandom",
                    r"SecurityException",
                    r"SecurityManager",
                    r"sendRedirect",
                    r"setAllowFileAccess",
                    r"setHeader",
                    r"setJavaScriptEnabled",
                    r"setPluginState",
                    r"setStatus",
                    r"SSLContext",
                    r"SSLSocketFactory",
                    r"Statement",
                    r"SUPPORT_DTD",
                    r"suppressAccessChecks",
                    r"TrustManager",
                    r"XMLReader",
                    r"readObject[\s]*\(",
                    r"printStackTrace[\s]\(",
                    r"SecretKeySpec"
                ],
                "jsp": [
                    r"request.getQueryString",
                    r"exec[\s]*\(.*\)",
                    r"Runtime\.",
                    r"getRuntime[\s]*\(.*\)(\.|\s*;)",
                    r"getRequest",
                    r"[Rr]equest.getParameter",
                    r"getProperty[\s]*\(",
                    r"java.security.acl.acl",
                    r"response.sendRedirect[\s]*\(.*(Request|request).*\)",
                    r"print[Ss]tack[Tt]race",
                    r"out\.print(ln)?.*[Rr]equest\.",
                    r"jdbc:.*;",
                    r"createStatement[\s]*\(.*\)",
                    r"executeQuery[\s]*\(.*\)",
                    r"Socket[\s]*\("
                ],
                "ssl": [
                    r"A[Ll][Ll][Oo][Ww]_?A[Ll][Ll]_?H[Oo][Ss][Tt][Nn][Aa][Mm][Ee]_?V[Ee][Rr][Ii][Ff][Ii][Ee][Rr]",
                    r"SSLSocketFactory",
                    r"is[Tt]rusted",
                    r"trustmanager"
                ],
                "xxe": [
                    r"SAXParserFactory",
                    r"DOM4J",
                    r"XMLInputFactory",
                    r"TransformerFactory",
                    r"javax.xml.validation.Validator",
                    r"SchemaFactory",
                    r"SAXTransformerFactory",
                    r"XMLReader",
                    r"SAXBuilder",
                    r"SAXReader",
                    r"javax.xml.bind.Unmarshaller",
                    r"XPathExpression",
                    r"DOMSource",
                    r"StAXSource"
                ],
                "serialization": [
                    r".*readObject\(.*",
                    r".*readResolve\(.*",
                    r"java.beans.XMLDecoder",
                    r"com.thoughtworks.xstream.XStream",
                    r".*\.fromXML\(.*\)",
                    r"com.esotericsoftware.kryo.io.Input",
                    r".readClassAndObject\(.*",
                    r".readObjectOrNull\(.*",
                    r"com.caucho.hessian.io",
                    r"com.caucho.burlap.io.BurlapInput",
                    r"com.caucho.burlap.io.BurlapOutput",
                    r"org.codehaus.castor",
                    r"[U|u]nmarshal",
                    r"jsonToJava\(.*",
                    r"JsonObjectsToJava\/.*",
                    r"JsonReader",
                    r"ObjectMapper\(",
                    r"enableDefaultTyping\(\s*\)",
                    r"@JsonTypeInfo\(",
                    r"readValue\(.*\,\s*Object\.class",
                    r"com.alibaba.fastjson.JSON",
                    r"JSON.parseObject",
                    r"com.owlike.genson.Genson",
                    r"useRuntimeType",
                    r"genson.deserialize",
                    r"org.red5.io",
                    r"deserialize\(.*\,\s*Object\.class",
                    r"\.Yaml",
                    r"\.load\(.*",
                    r"\.loadType\(.*\,\s*Object\.class",
                    r"YamlReader",
                    r"com.esotericsoftware.yamlbeans"
                ]
            },
            "owasp": {
                "apache": [
                    r"exec",
                    r"sprint",
                    r"document.referrer",
                    r"fprintf",
                    r"printf",
                    r"Stdio",
                    r"FILE",
                    r"strcpy",
                    r"strncpy",
                    r"Strcat",
                    r"cout",
                    r"cln",
                    r"cerr",
                    r"System",
                    r"popen",
                    r"stringstream",
                    r"fstringstream",
                    r"Malloc",
                    r"free",
                    r"headers_in",
                    r"ap_read_request",
                    r"post_read_request",
                    r"headers_out",
                    r"ap_rprintf",
                    r"ap_send_error_response",
                    r"ap_send_fd",
                    r"ap_vprintf",
                    r"headers_in",
                    r"headers_out",
                    r"headers_out",
                    r"ap_cookie_write2",
                    r"ap_cookie_read",
                    r"ap_cookie_check_string",
                    r"cout",
                    r"cerr",
                    r"ap_open_stderr_log",
                    r"ap_error_log2stderr",
                    r"ap_log_error",
                    r"ap_log_perror",
                    r"ap_log_rerror",
                    r"ap_unescape_all",
                    r"ap_unescape_url",
                    r"ap_unescape_url_keep2f",
                    r"ap_unescape_urlencoded",
                    r"ap_escape_path_segment"
                ],
                "asp": [
                    r"Request",
                    r"Request.QueryString",
                    r"Request.Form",
                    r"Request.ServerVariables",
                    r"Query_String",
                    r"hidden",
                    r"include",
                    r".int",
                    r"Response.Write",
                    r"Response.BinaryWrite",
                    r"<%=",
                    r".cookies",
                    r"err.",
                    r"Server.GetLastError",
                    r"On",
                    r"Error",
                    r"Resume",
                    r"Next",
                    r"On",
                    r"Error",
                    r"Goto",
                    r"0",
                    r"location.href",
                    r"location.replace",
                    r"method\=\"GET\"",
                    r"On",
                    r"Error",
                    r"Goto",
                    r"0",
                    r"commandText",
                    r"select",
                    r"from",
                    r"update",
                    r"insert",
                    r"into",
                    r"delete",
                    r"from",
                    r"where",
                    r"IRowSet",
                    r"execute",
                    r".execute",
                    r".open",
                    r"ADODB",
                    r"Commandtype",
                    r"ICommand",
                    r"session.timeout",
                    r"session.abandon",
                    r"session.removeall",
                    r"server.ScriptTimeour",
                    r"IsCLientConnected",
                    r"WriteEntry",
                    r"Response.AddHeader",
                    r"Response.AppendHeader",
                    r"Response.Redirect",
                    r"Response.Status",
                    r"Response.StatusCode",
                    r"Server.Transfer",
                    r"Server.Execute"
                ],
                "dotnet": [
                    r"request.accesstypes",
                    r"request.browser",
                    r"request.files",
                    r"request.headers",
                    r"request.TotalBytes",
                    r"request.httpmethod",
                    r"request.querystring",
                    r"request.item",
                    r"request.form",
                    r"request.BinaryRead",
                    r"request.cookies",
                    r"request.certificate",
                    r"request.rawurl",
                    r"request.servervariables",
                    r"request.url",
                    r"request.urlreferrer",
                    r"request.useragent",
                    r"request.userlanguages",
                    r"response.write",
                    r"innerText",
                    r"HttpUtility",
                    r"InnerHTML",
                    r"HtmlEncode",
                    r"<%=",
                    r"UrlEncode",
                    r"exec",
                    r"sp_",
                    r"delete",
                    r"from",
                    r"where",
                    r"exec",
                    r"@",
                    r"setfilter",
                    r"sqloledb",
                    r".Provider",
                    r"ExecuteReader",
                    r"SqlDataReader",
                    r"select",
                    r"from",
                    r"delete",
                    r"execute",
                    r"@",
                    r"executeQuery",
                    r"sql",
                    r"server",
                    r"System.Data.sql",
                    r"DataSource",
                    r"ExecuteReader",
                    r"insert",
                    r"execute",
                    r"sp_",
                    r"executestatement",
                    r"GetQueryResultInXML",
                    r"driver",
                    r"ADODB.recordset",
                    r"SqlCommand",
                    r"SqlDataAdapter",
                    r"update",
                    r"exec",
                    r"xp_",
                    r"executeSQL",
                    r"adodb",
                    r"Server.CreateObject",
                    r"New",
                    r"OleDbConnection",
                    r"Microsoft.Jet",
                    r"StoredProcedure",
                    r"System.Net.Cookie",
                    r"HTTPOnly",
                    r"document.cookie",
                    r"HTMLEncode",
                    r"<embed>",
                    r"<img>",
                    r"<meta>",
                    r"URLEncode",
                    r"<frame>",
                    r"<style>",
                    r"<object>",
                    r"<applet>",
                    r"<html>",
                    r"<layer>",
                    r"<frame",
                    r"security",
                    r"<frameset>",
                    r"<iframe>",
                    r"<ilayer>",
                    r"<iframe",
                    r"security",
                    r"htmlcontrols.htmlinputhidden",
                    r"webcontrols.label",
                    r"webcontrols.dropdownlist",
                    r"webcontrols.hiddenfield",
                    r"webcontrols.linkbutton",
                    r"webcontrols.hyperlink",
                    r"webcontrols.listbox",
                    r"webcontrols.textbox",
                    r"webcontrols.checkboxlist",
                    r"requestEncoding",
                    r"compilation",
                    r"webcontrols.dropdownlist",
                    r"httpRuntime",
                    r"forms",
                    r"protection",
                    r"connectionStrings",
                    r"Credentials",
                    r"responseEncoding",
                    r"webcontrols.linkbutton",
                    r"CustomErrors",
                    r"sessionState",
                    r"appSettings",
                    r"authentication",
                    r"mode",
                    r"identity",
                    r"impersonate",
                    r"Trace",
                    r"webcontrols.listbox",
                    r"httpCookies",
                    r"maxRequestLength",
                    r"ConfigurationSettings",
                    r"Allow",
                    r"timeout",
                    r"authorization",
                    r"webcontrols.checkboxlist",
                    r"httpHandlers",
                    r"Debug",
                    r"appSettings",
                    r"Deny",
                    r"remote",
                    r"Application_OnAuthenticateRequest",
                    r"Application_OnAUthorizeRequest",
                    r"Session_OnStart",
                    r"Session_OnEnd",
                    r"log4net",
                    r"Console.WriteLine",
                    r"System.Diagnostics.Debug",
                    r"System.Diagnostics.Trace",
                    r"validateRequest",
                    r"enableViewState",
                    r"enableViewStateMac",
                    r"Thread",
                    r"Dispose",
                    r"Public",
                    r"Sealed",
                    r"Serializable",
                    r"StrongNameIdentity",
                    r"AllowPartiallyTrustedCallersAttribute",
                    r"StrongNameIdentityPermission",
                    r"GetObjectData",
                    r"System.Reflection",
                    r"catch",
                    r"finally",
                    r"trace",
                    r"enabled",
                    r"customErrors",
                    r"mode",
                    r"RNGCryptoServiceProvider",
                    r"DES",
                    r"xor",
                    r"SHA",
                    r"RC2",
                    r"System.Security.Cryptography",
                    r"MD5",
                    r"System.Random",
                    r"base64",
                    r"Random",
                    r"SecureString",
                    r"ProtectedMemory",
                    r"RequestMinimum",
                    r"CodeAccessPermission",
                    r"SkipVerification",
                    r"ControlDomainPolicy",
                    r"RequestOptional",
                    r"MemberAccess",
                    r"ControlEvidence",
                    r"ControlPolicy",
                    r"Assert",
                    r"ControlAppDomain",
                    r"SerializationFormatter",
                    r"Debug.Assert",
                    r"UnmanagedCode",
                    r"ControlPrincipal",
                    r"printf",
                    r"strcpy"
                ],
                "java": [
                    r"FileInputStream",
                    r"ObjectInputStream",
                    r"FilterInputStream",
                    r"PipedInputStream",
                    r"SequenceInputStream",
                    r"StringBufferInputStream",
                    r"BufferedReader",
                    r"ByteArrayInputStream",
                    r"java.io.FileOutputStream",
                    r"File",
                    r"ObjectInputStream",
                    r"PipedInputStream",
                    r"StreamTokenizer",
                    r"getResourseAsStream",
                    r"java.io.FileReader",
                    r"java.io.FileWriter",
                    r"java.io.RandomAccessFile",
                    r"java.io.File",
                    r"renameTo",
                    r"Mkdir",
                    r"javax.servlet.\*",
                    r"getParameterNames",
                    r"getParameterValues",
                    r"getParameters",
                    r"getParameterMap",
                    r"getScheme",
                    r"getProtocol",
                    r"getContentType",
                    r"getServerName",
                    r"getRemoteAddr",
                    r"getRemoteHost",
                    r"getRealPath",
                    r"getLocalName",
                    r"getAttribute",
                    r"getAttributeNames",
                    r"getLocalAddr",
                    r"getAuthType",
                    r"getRemoteUser",
                    r"getCookies",
                    r"IsSecure",
                    r"HttpServletRequest",
                    r"getQueryString",
                    r"getHeaderNames",
                    r"getHeaders",
                    r"getPrincipal",
                    r"getUserPrincipal",
                    r"isUserInRole",
                    r"getInputStream",
                    r"getOutputStream",
                    r"getWriter",
                    r"addCookie",
                    r"addHeade",
                    r"setHeader",
                    r"setAttribute",
                    r"putValue",
                    r"javax.servlet.http.Cookie",
                    r"getName",
                    r"getPath",
                    r"getDomain",
                    r"getComment",
                    r"getMethod",
                    r"getPath",
                    r"getReader",
                    r"getRealPath",
                    r"getRequestURI",
                    r"getRequestURL",
                    r"getServerName",
                    r"getValue",
                    r"getValueNames",
                    r"getRequestedSessionId",
                    r"javax.servlet.ServletOutputStream",
                    r"strcpy",
                    r"javax.servlet.http.HttpServletResponse.sendRedirect",
                    r"strcpy",
                    r"setHeader",
                    r"sendRedirect",
                    r"setStatus",
                    r"addHeader",
                    r"etHeader",
                    r"java.sql.Connection.prepareStatement",
                    r"java.sql.ResultSet.getObject",
                    r"select",
                    r"insert",
                    r"java.sql.Statement.executeUpdate",
                    r"java.sql.Statement.addBatch",
                    r"execute",
                    r"executestatement",
                    r"createStatement",
                    r"java.sql.ResultSet.getString",
                    r"executeQuery",
                    r"jdbc",
                    r"java.sql.Statement.executeQuery",
                    r"java.sql.Statement.execute",
                    r"delete",
                    r"update",
                    r"java.sql.Connection.prepareCall",
                    r"com.sun.net.ssl",
                    r"SSLContext",
                    r"SSLSocketFactory",
                    r"TrustManagerFactory",
                    r"HttpsURLConnection",
                    r"KeyManagerFactory",
                    r"getSession",
                    r"Invalidate",
                    r"getId",
                    r"java.lang.Runtime.exec",
                    r"java.lang.Runtime.getRuntime",
                    r"getId",
                    r"java.io.PrintStream.write",
                    r"log4j",
                    r"jLo",
                    r"Lumberjack",
                    r"MonoLog",
                    r"qflog",
                    r"just4log",
                    r"log4Ant",
                    r"JDLabAgent",
                    r"document.write",
                    r"eval",
                    r"document.cookie",
                    r"window.location",
                    r"document.URL",
                    r"document.URL"
                ],
                "javascript": [
                    r"eval",
                    r"document.cookie",
                    r"document.referrer",
                    r"document.attachEvent",
                    r"document.body",
                    r"document.body.innerHtml",
                    r"document.body.innerText",
                    r"document.close",
                    r"document.create",
                    r"document.execCommand",
                    r"document.forms[0].action",
                    r"document.location",
                    r"document.open",
                    r"document.URL",
                    r"document.URLUnencoded",
                    r"document.write",
                    r"document.writeln",
                    r"location.hash",
                    r"location.href",
                    r"location.search",
                    r"window.alert",
                    r"window.attachEvent",
                    r"window.createRequest",
                    r"window.execScript",
                    r"window.location",
                    r"window.open",
                    r"window.navigate",
                    r"window.setInterval",
                    r"window.setTimeout",
                    r"XMLHTTP"
                ]
            },
            "perl": {
                "exec": [
                    r"exec(\s*\(|\s+).*\$.*\)?",
                    r"fork(\s*\(|\s+).*\)?",
                    r"`.*\$.*`",
                    r"system(\s*\(?|\s+)*\$.*\)?",
                    r"open(\s*\(?|\s+)*\$.*\)?"
                ],
                "perl.original": [
                    r"getc",
                    r"readdir",
                    r"read",
                    r"sysread",
                    r"exec",
                    r"eval",
                    r"fork",
                    r"`.*`",
                    r"fctnl",
                    r"ioctl",
                    r"bind",
                    r"setpgrp",
                    r"syscall",
                    r"connect",
                    r"system",
                    r"glob",
                    r"open",
                    r"mkdir",
                    r"rmdir",
                    r"link",
                    r"unlink",
                    r"chmod",
                    r"chown",
                    r"chroot",
                    r"symlink",
                    r"truncate",
                    r"kill",
                    r"umask",
                    r"param.*\(.*\);"
                ],
                "superglobal": [
                    r"\$ARGV\[.*?\]",
                    r"\$ARGC",
                    r"\$ENV"
                ],
                "todo": [
                    r"getc",
                    r"readdir(\s+|\s*\().*\$.*",
                    r"read(\s+|\s*\().*\$.*",
                    r"sysread",
                    r"eval.*\$.*",
                    r"fctnl",
                    r"ioctl",
                    r"bind",
                    r"setpgrp",
                    r"syscall",
                    r"connect.*\$.*",
                    r"glob(\s+|\s*\().*\$.*",
                    r"mkdir(\s+|\s*\().*\$.*",
                    r"rmdir(\s+|\s*\().*\$.*",
                    r"link(\s+|\s*\().*\$.*",
                    r"unlink(\s+|\s*\().*\$.*",
                    r"chmod(\s+|\s*\().*\$.*",
                    r"chown(\s+|\s*\().*\$.*",
                    r"chroot",
                    r"symlink",
                    r"truncate(\s+|\s*\().*\$.*",
                    r"kill.*\$.*",
                    r"umask",
                    r"->param\s*\(.*\)"
                ],
                "xss": [
                    r"print\s*.*\$.*->param\(?.*\)?"
                ]
            },
            "php": {
                "callbacks": [
                    r"ob_start",
                    r"array_diff_uassoc",
                    r"array_diff_ukey",
                    r"array_filter",
                    r"array_intersect_uassoc",
                    r"array_intersect_ukey",
                    r"array_map",
                    r"array_reduce",
                    r"array_udiff_assoc",
                    r"array_udiff_uassoc",
                    r"array_udiff",
                    r"array_uintersect_assoc",
                    r"array_uintersect_uassoc",
                    r"array_uintersect",
                    r"array_walk_recursive",
                    r"array_walk",
                    r"assert_options",
                    r"uasort",
                    r"uksort",
                    r"usort",
                    r"preg_replace_callback",
                    r"spl_autoload_register",
                    r"iterator_apply",
                    r"call_user_func",
                    r"call_user_func_array",
                    r"register_shutdown_function",
                    r"register_tick_function",
                    r"set_error_handler",
                    r"set_exception_handler",
                    r"session_set_save_handler",
                    r"sqlite_create_aggregate",
                    r"sqlite_create_function"
                ],
                "hashes": [
                    r"sha1\s*\(\s*[\w|\$|\"|\']*\s*\."
                ],
                "exec": [
                    r"assert([\s]*\(|[\s]+).*\)?",
                    r"exec([\s]*\(|[\s]+).*\)?",
                    r"`.*`",
                    r"passthru([\s]*\(|[\s]+).*\)?",
                    r"popen([\s]*\(|[\s]+).*\)?",
                    r"proc_close([\s]*\(|[\s]+).*\)?",
                    r"proc_open([\s]*\(|[\s]+).*\)?",
                    r"proc_get_status([\s]*\(|[\s]+).*\)?",
                    r"proc_nice([\s]*\(|[\s]+).*\)?",
                    r"proc_terminate([\s]*\(|[\s]+).*\)?",
                    r"shell_exec([\s]*\(|[\s]+).*\)?",
                    r"system([\s]*\(|[\s]+).*\)?"
                ],
                "extensions": [
                    r"expect_",
                    r"pcntl_",
                    r"posix_",
                    r"ftok",
                    r"msg_get_queue",
                    r"msg_queue_exists",
                    r"msg_receive",
                    r"msg_remove_queue",
                    r"msg_send",
                    r"msg_set_queue",
                    r"msg_stat_queue",
                    r"sem_",
                    r"shm_",
                    r"shmop_",
                    r"registerPhpFunctions"
                ],
                "info": [
                    r"phpinfo\s*\(.*\)",
                    r"phpcredits\s*\(.*\)",
                    r"php_logo_guid\s*\(.*\)",
                    r"php_uname\s*\(.*\)",
                    r"phpversion\s*\(.*\)",
                    r"zend_logo_guid\s*\(.*\)",
                    r"zend_version\s*\(.*\)",
                    r"get_loaded_extensions\s*\(.*\)"
                ],
                "php.original": [
                    r"exec.*\(.*\)",
                    r"`.*`",
                    r"passthru.*\(.*\)",
                    r"popen.*\(.*\)",
                    r"proc_close.*\(.*\)",
                    r"proc_open.*\(.*\)",
                    r"proc_get_status.*\(.*\)",
                    r"proc_nice.*\(.*\)",
                    r"proc_terminate.*\(.*\)",
                    r"proc_close.*\(.*\)",
                    r"proc_open.*\(.*\)",
                    r"proc_get_status.*\(.*\)",
                    r"proc_nice.*\(.*\)",
                    r"proc_terminate.*\(.*\)",
                    r"shell_exec.*\(.*\)",
                    r"system.*\(.*\)",
                    r"expect_",
                    r"pcntl_",
                    r"posix_",
                    r"ftok",
                    r"msg_get_queue",
                    r"msg_queue_exists",
                    r"msg_receive",
                    r"msg_remove_queue",
                    r"msg_send",
                    r"msg_set_queue",
                    r"msg_stat_queue",
                    r"sem_",
                    r"shm_",
                    r"shmop_",
                    r"header.*\(.*\$_(GET|POST|REQUEST|COOKIE).*\)",
                    r"eval\s*\(\s*.\$.*\s*\)",
                    r"file.*\(.\$.*\)",
                    r"file_get_contents.*\(.\$.*\)",
                    r"fopen.*\(.*\$.*\)",
                    r"fwrite",
                    r"move_uploaded_file.*\(.*\)",
                    r"stream_",
                    r"create_function.*\(.*\)",
                    r"mail.*\(.\$.*\)",
                    r"include.*\(.*\$.*\)",
                    r"include_once.*\(.*\$.*\)",
                    r"preg_replace.*\(.\$*\)",
                    r"readfile.*\(.\$.*\)",
                    r"require.*\(.*\$.*\)",
                    r"require_once.*\(.*\$.*\)",
                    r"phpinfo.*\(.*\)",
                    r"phpcredits.*\(.*\)",
                    r"php_logo_guid.*\(.*\)",
                    r"php_uname.*\(.*\)",
                    r"phpversion.*\(.*\)",
                    r"zend_logo_guid.*\(.*\)",
                    r"zend_version.*\(.*\)",
                    r"get_loaded_extensions.*\(.*\)",
                    r"unserialize.*\(.*\)",
                    r"unserialize_callback_func",
                    r"mysql_connect.*\(.*\$.*\)",
                    r"mysql_pconnect.*\(.*\$.*\)",
                    r"mysql_change_user.*\(.*\$.*\)",
                    r"mysql_query.*\(.*\$.*\)",
                    r"mysql_error.*\(.*\$.*\)",
                    r"mysql_set_charset.*\(.*\$.*\)",
                    r"mysql_unbuffered_query.*\(.*\$.*\)",
                    r"pg_connect.*\(.*\$.*\)",
                    r"pg_pconnect.*\(.*\$.*\)",
                    r"pg_execute.*\(.*\$.*\)",
                    r"pg_insert.*\(.*\$.*\)",
                    r"pg_put_line.*\(.*\$.*\)",
                    r"pg_query.*\(.*\$.*\)",
                    r"pg_select.*\(.*\$.*\)",
                    r"pg_send_query.*\(.*\$.*\)",
                    r"pg_set_client_encoding.*\(.*\$.*\)",
                    r"pg_update.*\(.*\$.*\)",
                    r"getenv.*\(.*\)",
                    r"apache_getenv.*\(.*\)",
                    r"putenv.*\(.*\)",
                    r"apache_setenv.*\(.*\)",
                    r"getallheaders.*\(.*\)",
                    r"apache_request_headers.*\(.*\)",
                    r"apache_response_headers.*\(.*\)",
                    r"\$_ENV\[.*\]",
                    r"\$_GET\[.*\]",
                    r"\$_POST\[.*\]",
                    r"\$_COOKIE\[.*\]",
                    r"\$_REQUEST\[.*\]",
                    r"\$_FILES\[.*\]",
                    r"\$PHPSELF",
                    r"\$HTTP_GET_VARS",
                    r"\$http_get_vars",
                    r"\$HTTP_POST_VARS",
                    r"\$http_post_vars",
                    r"\$HTTP_ENV_VARS",
                    r"\$http_env_vars",
                    r"\$HTTP_POST_FILES",
                    r"\$http_post_files"
                ],
                "sql": [
                    r"mysql_connect[\s]*\(.*\$.*\)",
                    r"mysql_pconnect[\s]*\(.*\$.*\)",
                    r"mysql_change_user[\s]*\(.*\$.*\)",
                    r"mysql_query[\s]*\(.*\$.*\)",
                    r"mysql_error[\s]*\(.*\$.*\)",
                    r"mysql_set_charset[\s]*\(.*\$.*\)",
                    r"mysql_unbuffered_query[\s]*\(.*\$.*\)",
                    r"mysqli_.*[\s]*\(.*\$.*\)",
                    r"pg_connect[\s]*\(.*\$.*\)",
                    r"pg_pconnect[\s]*\(.*\$.*\)",
                    r"pg_execute[\s]*\(.*\$.*\)",
                    r"pg_insert[\s]*\(.*\$.*\)",
                    r"pg_put_line[\s]*\(.*\$.*\)",
                    r"pg_query[\s]*\(.*\$.*\)",
                    r"pg_select[\s]*\(.*\$.*\)",
                    r"pg_send_query[\s]*\(.*\$.*\)",
                    r"pg_set_client_encoding[\s]*\(.*\$.*\)",
                    r"pg_update[\s]*\(.*\$.*\)",
                    r"sqlite_open[\s]*\(.*\$.*\)",
                    r"sqlite_poen[\s]*\(.*\$.*\)",
                    r"sqlite_query[\s]*\(.*\$.*\)",
                    r"sqlite_array_query[\s]*\(.*\$.*\)",
                    r"sqlite_create_function[\s]*\(.*\$.*\)",
                    r"sqlite_create_aggregate[\s]*\(.*\$.*\)",
                    r"sqlite_exec[\s]*\(.*\$.*\)",
                    r"sqlite_fetch_.*[\s]*\(.*\$.*\)",
                    r"msql_.*[\s]*\(.*\$.*\)",
                    r"mssql_.*[\s]*\(.*\$.*\)",
                    r"odbc_.*[\s]*\(.*\$.*\)",
                    r"fbsql_.*[\s]*\(.*\$.*\)",
                    r"sybase_.*[\s]*\(.*\$.*\)",
                    r"ibase_.*[\s]*\(.*\$.*\)",
                    r"dbx_.*[\s]*\(.*\$.*\)",
                    r"ingres_.*[\s]*\(.*\$.*\)",
                    r"ifx_.*[\s]*\(.*\$.*\)",
                    r"oci_.*[\s]*\(.*\$.*\)",
                    r"sqlsrv_.*[\s]*\(.*\$.*\)",
                    r"px_.*[\s]*\(.*\$.*\)",
                    r"ovrimos_.*[\s]*\(.*\$.*\)",
                    r"maxdb_.*[\s]*\(.*\$.*\)",
                    r"db2_.*[\s]*\(.*\$.*\)"
                ],
                "ssl": [
                    r"CURLOPT_SSL_VERIFY(HOST|PEER),.*([Ff][Aa][Ll][Ss][Ee]|0)"
                ],
                "streams.php": [
                    r"unserialize[\s]*\(.*\$",
                    r"file_exists[\s]*\(.*\$",
                    r"md5_file[\s]*\(.*\$",
                    r"filemtime[\s]*\(.*\$",
                    r"filesize[\s]*\(.*\$",
                    r"file_get_contents[\s]*\(.*\$",
                    r"fopen[\s]*\(.*\$",
                    r"file[\s]*\(.*\$",
                    r"php://stdin",
                    r"php://stdout",
                    r"php://stderr",
                    r"php://output",
                    r"php://input",
                    r"php://filter",
                    r"php://memory",
                    r"php://temp",
                    r"phar://.*\$",
                    r"expect://"
                ],
                "superglobal": [
                    r"getenv\s*\(.*\)",
                    r"apache_getenv\s*\(.*\)",
                    r"putenv\s*\(.*\)",
                    r"apache_setenv\s*\(.*\)",
                    r"getallheaders\s*\(.*\)",
                    r"apache_request_headers\s*\(.*\)",
                    r"apache_response_headers\s*\(.*\)",
                    r"\$_ENV\[.*\]",
                    r"\$_GET\[.*\]",
                    r"\$_POST\[.*\]",
                    r"\$_COOKIE\[.*\]",
                    r"\$_REQUEST\[.*\]",
                    r"\$_FILES\[.*\]",
                    r"\$_SERVER\[.*\]",
                    r"\$PHPSELF",
                    r"\$HTTP_GET_VARS",
                    r"\$http_get_vars",
                    r"\$HTTP_POST_VARS",
                    r"\$http_post_vars",
                    r"\$HTTP_ENV_VARS",
                    r"\$http_env_vars",
                    r"\$HTTP_RAW_POST_DATA",
                    r"\$http_raw_post_data",
                    r"\$HTTP_POST_FILES",
                    r"\$http_post_files",
                    r"\$\$.*"
                ],
                "deserialization": [
                    r"unserialize\s*\(",
                    r"unserialize_callback_func"
                ],
                "deserialization-gadgets": [
                    r"function\s+__[w|W]ake[u|U]p\s*\(",
                    r"function\s+__[d|D]setruct\s*\(",
                    r"function\s+__[c|C]onstruct\s*\(",
                    r"function\s+__to[s|S]tring\s*\("
                ],
                "todo": [
                    r"header\s*\(.*\$_(GET|POST|REQUEST|COOKIE).*\)",
                    r"eval\s*\(\s*.\$.*\s*\)",
                    r"file\s*\(.\$.*\)",
                    r"file_get_contents\s*\(.\$.*\)",
                    r"fopen\s*\(.*\$.*\)",
                    r"p?fsockopen\s*\(.*\)",
                    r"stream_context_create\s*\(.*\)",
                    r"fwrite",
                    r"move_uploaded_file\s*\(.*\)",
                    r"stream_",
                    r"create_function\s*\(.*\)",
                    r"mail\s*\(.\$.*\)",
                    r"include\s*\(.*\$.*\)",
                    r"include_once\s*\(.*\$.*\)",
                    r"preg_replace\s*\(.\$*\)",
                    r"readfile\s*\(.\$.*\)",
                    r"require\s*\(.*\$.*\)",
                    r"require_once\s*\(.*\$.*\)",
                    r"unserialize\s*\(.*\)",
                    r"unserialize_callback_func"
                ],
                "xss": [
                    r"echo[\s]+.*\$(_ENV|_GET|_POST|_COOKIE|_REQUEST|_SERVER|HTTP|http).*",
                    r"print[\s]+.*\$(_ENV|_GET|_POST|_COOKIE|_REQUEST|_SERVER|HTTP|http).*",
                    r"print_r([\s]*\(|[\s]+).*\)?\$(_ENV|_GET|_POST|_COOKIE|_REQUEST|_SERVER|HTTP|http).*",
                    r"\<\?\=\$(_ENV|_GET|_POST|_COOKIE|_REQUEST|_SERVER|HTTP|http)",
                    r"\<\%\=\$(_ENV|_GET|_POST|_COOKIE|_REQUEST|_SERVER|HTTP|http)"
                ],
                "xxe": [
                    r"loadXML\s*\(.*\$.*",
                    r"xml_parse\s*\(.*\$.*",
                    r"simplexml_load_string\s*\(.*\$.*",
                    r"simplexml_import_dom\s*\(.*\$.*",
                    r"readOuterXML\s*\(.*\$.*",
                    r"readInnerXML\s*\(.*\$.*",
                    r"XMLReader",
                ],
            },
            "python": {
                "original": [
                    r"access[\s]*\(",
                    r"assert[\s]*\(",
                    r"mkfifo",
                    r"pathconf",
                    r"listdir",
                    r"open[\s]*\(",
                    r"lstat",
                    r"stat[\s]*\(",
                    r"chmod[\s]*\(",
                    r"chown[\s]*\(",
                    r"rename[\s]*\(",
                    r"mkdir[\s]*\(",
                    r"rmdir",
                    r"remove[\s]*\(",
                    r"\.unlink[\s]*\(",
                    r"link[\s]*\(",
                    r"execv[\s]\(",
                    r"execve[\s]*\(",
                    r"execl[\s]*\(",
                    r"execlp[\s]*\(",
                    r"execle[\s]*\(",
                    r"execvp[\s]*\(",
                    r"\.system[\s]*\(.*\)",
                    r"[Pp]open[\s]*\(",
                    r"openpty[\s]*\(",
                    r"[Pp][Ii][Pp][Ee][\s]*\(",
                    r"pipes",
                    r"exec[\s]*\(",
                    r"spawn",
                    r"shell",
                    r"subprocess",
                    r"execfile",
                    r"eval[\s]*\(",
                    r"input[\s]*\(",
                    r"compile",
                    r"tmpfile",
                    r"tmpnam",
                    r"getlogin",
                    r"ttyname",
                    r"raw_input",
                    r"read[\s]*\(",
                    r"recvfrom",
                    r"recv",
                    r"signal",
                    r"fork[\s]*\(",
                    r"[Bb]astion",
                    r"[Rr][Ee]xec",
                    r"r_eval",
                    r"r_execfile",
                    r"r_exec",
                    r"[\s]+commands",
                    r"[\s]+input",
                    r"pickle",
                    r"c[Pp]ickle",
                    r"shell[\s]*=[\s]*[Ff]alse",
                    r"Cookie",
                    r"SmartCookie",
                    r"SerialParser",
                    r"multiprocessing",
                    r"shelve",
                    r"tarfile",
                    r"zipfile",
                    r"[\s]+ast",
                    r"[\s]+parser",
                    r"[\s]+compiler",
                    r"yaml",
                    r"urllib3.disable_warnings"
                ]
            },
            "nodejs": {
                "exec": [
                    r"require([\s]*)\(([\s]*)'child_process'([\s]*)\)",
                    r"eval([\s]*)\(",
                    r"(setInterval|setTimeout|new([\s]*)Function)([\s]*)\(([\s]*)\".*\"",
                    r"(setInterval|setTimeout|new([\s]*)Function)([\s]*)\(([\s]*)",
                    r"(eval\()(.{0,40000})(req\.|req\.query|req\.body|req\.param)",
                    r"(setTimeout\()(.{0,40000})(req\.|req\.query|req\.body|req\.param)",
                    r"(setInterval\()(.{0,40000})(req\.|req\.query|req\.body|req\.param)",
                    r"(new Function\()(.{0,40000})(req\.|req\.query|req\.body|req\.param)",
                    r"(deserialize\(|unserialize\()",
                    r"(require\('js-yaml'\)\.load\(|yaml\.load\()",
                    r"(\.exec\()(.{0,40000})(req\.|req\.query|req\.body|req\.param)",
                    r"(\.exec\()"
                ],
                "ssl": [
                    r"(\[)*('|\")*NODE_TLS_REJECT_UNAUTHORIZED('|\")*(\])*(\s)*=(\s)*('|\")*0('|\")*",
                    r"SSL_VERIFYPEER(\s)*:(\s)*0"
                ],
                "csrf": [
                    r"csrf"
                ],
                "ssrf": [
                    r"require( )*(\()( *)('|\")(request|needle)('|\")( *)(\))",
                    r"(\()(.*?)(req\.|req\.query|req\.body|req\.param)",
                    r"\.get( *)(\()(.*?)(req\.|req\.query|req\.body|req\.param)"
                ],
                "weak-hash": [
                    r"createHash\(('|\")md5('|\")",
                    r"createHash\(('|\")sha1('|\")"
                ],
                "tempfiles": [
                    r"bodyParser\(.*\)"
                ],
                "dirtrav": [
                    r"(\.createReadStream\()(.{0,40000})(req\.|req\.query|req\.body|req\.param)",
                    r"(\.readFile\()(.{0,40000})(req\.|req\.query|req\.body|req\.param)",

                ],
                "sql": [
                    r"\.(execQuery|query)([\s]*)\(([\s]*)\".*\".*\+",
                    r"\.(createConnection|connect)([\s]*)\(",
                    r"(SELECT|INSERT|UPDATE|DELETE|CREATE|EXPLAIN)(.{0,40000})(req\.|req\.query|req\.body|req\.param)",
                    r"(\.)(find|drop|create|explain|delete|count|bulk|copy)(.{0,4000})({(.{0,4000})\$where:)(.{0,4000})\
                        (req\.|req\.query|req\.body|req\.param)",

                ],
                "xss": [
                    r"(window.)?location(([\s]*)|\.)(href)?\=",
                    r"handlebars.SafeString",
                    r"noEscape(\s)*:(\s)*true",
                    r"lusca.xssProtection\(false\)|X-XSS-Protection('|\")*(\s)*(:|,)(\s)*('|\")*0",
                    r"(res\.(write|send)\()(.{0,40000})(req\.|req\.query|req\.body|req\.param)",
                    r"{{{\s*[\w.\[\]\(\)]+\s*}}}",
                    r"{\s*[\w.\[\]\(\)]+\s*\|\s*s\s*}",
                    r"#{\s*[\w.\[\]\(\)\'\"]+\s*}",
                    r"&lt;%-\s*[\w.\[\]\(\)]+\s*%&gt;",
                    r"&lt;%-\s*@+[\w.\[\]\(\)]+\s*%&gt;",

                ],
                "hardcoded": [
                    r"\"(username|user|password|pass)\"([\s]*):([\s]*)\".*\"",
                    r"\"port\.*\"([\s]*):([\s]*)\d+",
                    r"password\s*=\s*['|\"].+['|\"]\s{0,5}[;|.]"
                    r"\s*['|\"]password['|\"]\s*:",
                    r"\s*['|\"]+secret['|\"]+\s*:|\s*secret\s*:\s*['|\"]+",
                    r"username\s*=\s*['|\"].+['|\"]\s{0,5}[;|.]",

                ],
                "misc": [
                    r"(res\.redirect\()( *)(req\.|req\.query|req\.body|req\.param)",
                    r"(res\.set\()(.{0,40000})(req\.|req\.query|req\.body|req\.param)"
                ]
            },
            "ruby": {
                "exec": [
                    r"_send_[\s]*\(",
                    r"__send__[\s]*\(",
                    r"`.*`",
                    r"system[\s]*\(",
                    r"open[\s]*\(",
                    r"send[\s]*\(",
                    r"public_send[\s]*\(",
                    r"eval[\s]*\(",
                    r"exec[\s]*\(",
                    r"syscall[\s]*\("
                ],
                "in-out": [
                    r"File\.new[\s]*\(",
                    r"fork[\s]*\(",
                    r"write[\s]*\(",
                    r"execve[\s]*\("
                ],
                "reflection": [
                    r"params\[:[\w]+\]\.constantize",
                    r"new[\s]*\(params\[:[\w]+\]"
                ],
                "serialization": [
                    r"Marshal.load\(",
                    r"YAML.load\("
                ]
            },
            "delphi": {
                "exec": [
                    r"uses ShellApi;",
                    r"ShellExecute\s*\(.*",
                    r"WinExec\s*\(.*",

                ],
                "unsafe": [
                    r"StrCopy\s*\(.*",
                    r"lstrcpy\s*\(.*",
                    r"strcat\s*\(.*",
                    r"strlen\s*\(.*",
                    r"strcmp\s*\(.*",
                    r"LoadLibrary\s*\(.*",
                ],
                "sources": [
                    r"(^|\s+)ParamString\s*\(.*",
                    r"(^|\s+)ReadLn\s*\(.*",
                    r"(^|\s+)ReadKey\s*\(.*",
                    r"(^|\s+)Read\s*\(.*"
                ],
                "sql": [
                    r"([\w]+)\.SQL\.Add\s*\(",
                    r"(^|\s+)(ALTER|CREATE|DELETE|DROP|EXEC(UTE){0,1}|INSERT( +INTO)"
                    r"{0,1}|MERGE|SELECT|UPDATE|UNION( +ALL){0,1})(\s)+"
                ],
                "csv": [
                    "TSdfDataset"
                ],
                "sensitive": [
                    r"\".*user\"",
                    r".*user",
                    r"\".*pass(wd|word)?\"",
                    r".*pass(wd|word)?",
                    r"\s+.*token\s+"
                ],
                "comments": [
                    r"^\s*//"
                ]
            }

        }
        if category is None:
            return signatures
        elif category in signatures.keys():
            if subcategory is None:
                return signatures[category]
            elif subcategory in signatures[category].keys():
                return signatures[category][subcategory]
            else:
                print("[-] Unknown subcategory")
                return signatures[category]
        else:
            print("[-] Unknown category")
            return signatures

    def get_categories(self):
        return self.signatures.keys()

    def print_categories(self):
        for c in self.signatures.keys():
            print("\t" + c)


def main():
    parser = argparse.ArgumentParser(description='Codegrepper - A simple code auditor by d3adc0de', add_help=True)

    parser.add_argument(
        '-d', '--directory', required=False, type=str, default=".", help='Directory to start enumeration')
    parser.add_argument(
        '-f', '--filter', required=False, type=str, default=None, help='File extension filter')
    parser.add_argument(
        '-r', '--regex', required=False, type=str, default=None, help='Custom regex')
    parser.add_argument(
        '-c', '--category', required=False, type=str, default=None, help='Category [# to get category list]')
    parser.add_argument(
        '-s', '--subcategory', required=False, type=str, default=None, help='Subcategories [# to get subcategory list]')
    parser.add_argument(
        '-i', '--insensitive', required=False, default=False, action='store_true', help='Case insensitive search')
    parser.add_argument(
        '-D', '--debug', required=False, default=False, action='store_true', help='Enable debug logging')
    parser.add_argument(
        '-I', '--includedir', required=False, type=str, action='append', default=None,
        help='Include only directory (regex)')
    parser.add_argument(
        '-L', '--context-lines', required=False, type=str, default=None, help='Include context lines')
    parser.add_argument(
        '-E', '--excludedir', required=False, type=str, action='append', default=None,
        help='Exclude directory (regex)')
    parser.add_argument(
        '-rx', '--excluderegex', required=False, type=str, action='append', default=None,
        help='Exclude regexes')
    parser.add_argument(
        '-nc', '--no-comments', required=False, default=False, action='store_true', help='Exclude comments')
    parser.add_argument(
        '--no-regex', required=False, default=False, action='store_true',
        help='Exclude [category][subcategory] from output')
    parser.add_argument(
        '-rel', '--relative-paths', required=False, default=False, action='store_true', help='Use relative paths')
    parser.add_argument(
        '-fo', '--files-only', required=False, default=False, action='store_true',
        help='Print only path of matching files')
    # parser.add_argument(
    #    '-ri', '--includeregex', required=False, type=str, default=None, help='File extension filter')

    args = parser.parse_args()

    advanced_filter = {
        "exclude-directory": [],
        "include-directory": [],
        "exclude-regexes": []
    }

    if args.excludedir:
        advanced_filter["exclude-directory"] = args.excludedir
    if args.includedir:
        advanced_filter["include-directory"] = args.includedir
    if args.excluderegex:
        advanced_filter["exclude-regexes"] = args.excluderegex

    if len(sys.argv) <= 1:
        parser.print_help()
        sys.exit()

    if (args.category or args.subcategory) and args.regex:
        print("[-] Regex based and category based solution cannot go together")
        parser.print_help()
        sys.exit()

    if args.subcategory and not args.category:
        print("[-] Cannot set a subcategory without a category")
        parser.print_help()
        sys.exit()

    if args.category == "#":
        print("[*] Categories:")
        CodeGrepper().print_categories()
    elif args.category is not None and args.subcategory == "#":
        category = args.category.lower()
        print("[*] Subcategories of {}:".format(category))
        CodeGrepper(category=category).print_categories()
    elif args.regex is not None:
        try:
            CodeGrepper(filter=args.filter, case_insensitive=args.insensitive, advanced_filter=advanced_filter,
                        exclude_comments=args.no_comments, debug=args.debug, context=args.context_lines,
                        files_only=args.files_only, relative_paths=args.relative_paths, no_regex=args.no_regex).audit(
                                                directory=args.directory, regex=args.regex)
        except Exception as e:
            print("[-] Something wrong happened")
            traceback.print_exc()
            print(e)
    else:
        try:
            category = args.category.lower() if args.category else None
            subcategory = args.subcategory.lower() if args.subcategory else None
            CodeGrepper(category=category, subcategory=subcategory, filter=args.filter,
                        case_insensitive=args.insensitive, advanced_filter=advanced_filter,
                        exclude_comments=args.no_comments, debug=args.debug, context=args.context_lines,
                        files_only=args.files_only, relative_paths=args.relative_paths, no_regex=args.no_regex
                        ).audit(args.directory)
        except Exception as e:
            print("[-] Something wrong happened")
            traceback.print_exc()
            print(e)


if __name__ == '__main__':
    os.system('color')
    main()
