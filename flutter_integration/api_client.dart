/// API Client for Threadly Backend
/// أضف هذا الملف إلى مشروع Flutter في: lib/services/api_client.dart
///
/// أضف للـ pubspec.yaml:
/// dependencies:
///   http: ^1.2.0
///   shared_preferences: ^2.2.2

import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

class ApiClient {
  // ⚠️ غيّر هذا حسب جهازك:
  // - Android Emulator: http://10.0.2.2:8000/api
  // - iOS Simulator: http://localhost:8000/api
  // - جهاز حقيقي: http://YOUR_LOCAL_IP:8000/api
  static const String baseUrl = 'http://10.0.2.2:8000/api';

  static String? _token;

  /// تحميل التوكن المحفوظ
  static Future<void> loadToken() async {
    final prefs = await SharedPreferences.getInstance();
    _token = prefs.getString('auth_token');
  }

  /// حفظ التوكن
  static Future<void> saveToken(String token) async {
    _token = token;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('auth_token', token);
  }

  /// حذف التوكن (logout)
  static Future<void> clearToken() async {
    _token = null;
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('auth_token');
  }

  /// Headers مع التوكن
  static Map<String, String> get _headers {
    return {
      'Content-Type': 'application/json',
      if (_token != null) 'Authorization': 'Bearer $_token',
    };
  }

  // ============ AUTH ============

  static Future<Map<String, dynamic>> signUp({
    required String email,
    required String password,
    required String name,
    String? phone,
  }) async {
    final response = await http.post(
      Uri.parse('$baseUrl/auth/signup'),
      headers: _headers,
      body: jsonEncode({
        'email': email,
        'password': password,
        'name': name,
        if (phone != null) 'phone': phone,
      }),
    );
    return _handleResponse(response);
  }

  static Future<Map<String, dynamic>> login({
    required String email,
    required String password,
  }) async {
    final response = await http.post(
      Uri.parse('$baseUrl/auth/login'),
      headers: _headers,
      body: jsonEncode({'email': email, 'password': password}),
    );
    final data = _handleResponse(response);
    if (data['access_token'] != null) {
      await saveToken(data['access_token']);
    }
    return data;
  }

  static Future<Map<String, dynamic>> getMe() async {
    final response = await http.get(
      Uri.parse('$baseUrl/auth/me'),
      headers: _headers,
    );
    return _handleResponse(response);
  }

  // ============ PRODUCTS ============

  static Future<List<dynamic>> listProducts({
    String? category,
    double? minPrice,
    double? maxPrice,
    String? size,
    String? search,
    int page = 1,
  }) async {
    final params = <String, String>{
      'page': '$page',
      if (category != null && category != 'All') 'category': category,
      if (minPrice != null) 'min_price': '$minPrice',
      if (maxPrice != null) 'max_price': '$maxPrice',
      if (size != null) 'size': size,
      if (search != null && search.isNotEmpty) 'search': search,
    };

    final uri = Uri.parse('$baseUrl/products').replace(queryParameters: params);
    final response = await http.get(uri, headers: _headers);
    return _handleResponse(response) as List<dynamic>;
  }

  static Future<Map<String, dynamic>> getProduct(String id) async {
    final response = await http.get(
      Uri.parse('$baseUrl/products/$id'),
      headers: _headers,
    );
    return _handleResponse(response);
  }

  static Future<Map<String, dynamic>> createProduct(
    Map<String, dynamic> data,
  ) async {
    final response = await http.post(
      Uri.parse('$baseUrl/products'),
      headers: _headers,
      body: jsonEncode(data),
    );
    return _handleResponse(response);
  }

  static Future<Map<String, dynamic>> toggleFavorite(String productId) async {
    final response = await http.post(
      Uri.parse('$baseUrl/products/$productId/favorite'),
      headers: _headers,
    );
    return _handleResponse(response);
  }

  static Future<List<dynamic>> getFavorites() async {
    final response = await http.get(
      Uri.parse('$baseUrl/products/me/favorites'),
      headers: _headers,
    );
    return _handleResponse(response) as List<dynamic>;
  }

  static Future<List<dynamic>> getMyListings() async {
    final response = await http.get(
      Uri.parse('$baseUrl/products/me/listings'),
      headers: _headers,
    );
    return _handleResponse(response) as List<dynamic>;
  }

  // ============ AI STYLIST ============

  static Future<Map<String, dynamic>> getStylistRecommendations({
    required String style,
    required String occasion,
    required String bodyType,
    required List<String> favoriteColors,
    required List<String> preferredCategories,
    double? budgetMin,
    double? budgetMax,
  }) async {
    final response = await http.post(
      Uri.parse('$baseUrl/stylist/recommend'),
      headers: _headers,
      body: jsonEncode({
        'style': style,
        'occasion': occasion,
        'body_type': bodyType,
        'favorite_colors': favoriteColors,
        'preferred_categories': preferredCategories,
        if (budgetMin != null) 'budget_min': budgetMin,
        if (budgetMax != null) 'budget_max': budgetMax,
      }),
    );
    return _handleResponse(response);
  }

  // ============ ORDERS ============

  static Future<Map<String, dynamic>> createOrder({
    required String productId,
    required String orderType, // 'purchase' or 'rental'
    DateTime? rentStart,
    DateTime? rentEnd,
    Map<String, dynamic>? shippingAddress,
  }) async {
    final response = await http.post(
      Uri.parse('$baseUrl/orders'),
      headers: _headers,
      body: jsonEncode({
        'product_id': productId,
        'order_type': orderType,
        if (rentStart != null) 'rent_start': rentStart.toIso8601String().split('T').first,
        if (rentEnd != null) 'rent_end': rentEnd.toIso8601String().split('T').first,
        if (shippingAddress != null) 'shipping_address': shippingAddress,
      }),
    );
    return _handleResponse(response);
  }

  static Future<List<dynamic>> getMyOrders() async {
    final response = await http.get(
      Uri.parse('$baseUrl/orders/me'),
      headers: _headers,
    );
    return _handleResponse(response) as List<dynamic>;
  }

  // ============ CHAT ============

  static Future<List<dynamic>> getChatThreads() async {
    final response = await http.get(
      Uri.parse('$baseUrl/chat/threads'),
      headers: _headers,
    );
    return _handleResponse(response) as List<dynamic>;
  }

  static Future<List<dynamic>> getMessages(String threadId) async {
    final response = await http.get(
      Uri.parse('$baseUrl/chat/threads/$threadId/messages'),
      headers: _headers,
    );
    return _handleResponse(response) as List<dynamic>;
  }

  static Future<Map<String, dynamic>> sendMessage({
    String? threadId,
    String? recipientId,
    String? productId,
    required String content,
  }) async {
    final response = await http.post(
      Uri.parse('$baseUrl/chat/messages'),
      headers: _headers,
      body: jsonEncode({
        if (threadId != null) 'thread_id': threadId,
        if (recipientId != null) 'recipient_id': recipientId,
        if (productId != null) 'product_id': productId,
        'content': content,
      }),
    );
    return _handleResponse(response);
  }

  // ============ UPLOADS ============

  static Future<Map<String, dynamic>> uploadImage(String filePath) async {
    final request = http.MultipartRequest(
      'POST',
      Uri.parse('$baseUrl/uploads/image'),
    );
    request.headers['Authorization'] = 'Bearer $_token';
    request.files.add(await http.MultipartFile.fromPath('file', filePath));

    final streamedResponse = await request.send();
    final response = await http.Response.fromStream(streamedResponse);
    return _handleResponse(response);
  }

  // ============ HELPERS ============

  static dynamic _handleResponse(http.Response response) {
    if (response.statusCode >= 200 && response.statusCode < 300) {
      if (response.body.isEmpty) return null;
      return jsonDecode(response.body);
    }

    final body = response.body.isNotEmpty ? jsonDecode(response.body) : {};
    final detail = body['detail'] ?? 'Unknown error';
    throw ApiException(response.statusCode, detail.toString());
  }
}


class ApiException implements Exception {
  final int statusCode;
  final String message;

  ApiException(this.statusCode, this.message);

  @override
  String toString() => 'API Error $statusCode: $message';
}
